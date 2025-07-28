import streamlit as st
import os
import json
from datetime import datetime

from core.auth import get_tenant_id, get_user_role, get_tenant_branding
from utils.file_utils import sanitize_filename
from core.security import redact_log, mask_phi
from core.audit import log_audit_event
from core.cache_utils import clear_caches
from core.error_handling import handle_error
from logger import logger
from core.db import get_templates
from utils.docx_utils import replace_text_in_docx_all
from services.dropbox_client import DropboxClient
from core.constants import DROPBOX_TEMPLATES_ROOT
from dropbox.files import WriteMode

CATEGORIES = {
    "Mediation Memo": "mediation",
    "Demand Letter": "demand",
    "FOIA Letter": "foia",
    "Batch Documents": "batch_docs",
    "Email Templates": "email"
}

def run_ui():
    st.header("📪 Template & Style Example Manager")

    try:
        tenant_id = get_tenant_id()
        branding = get_tenant_branding(tenant_id)
        st.caption(f"Tenant: {branding.get('firm_name', tenant_id)}")
    except Exception as e:
        msg = handle_error(e, code="TEMPLATE_UI_002")
        st.error(msg)
        return

    if get_user_role() != "admin":
        st.warning("⚠️ Only Admins can manage templates.")
        return

    tab1, tab2, tab3 = st.tabs(["📂 Templates", "🖋️ Style Examples", "🎨 Branding"])
    client = DropboxClient()

    # ---------------- Tab 1 ----------------
    with tab1:
        try:
            selected_category_label = st.selectbox(
                "Choose Template Category", list(CATEGORIES.keys()), key="template_category"
            )
            selected_category = CATEGORIES[selected_category_label]

            st.subheader(f"📁 {selected_category_label} Templates")

            allowed_types = ["txt"] if selected_category == "email" else ["docx"]
            upload_label = "Upload Template (.txt)" if selected_category == "email" else "Upload Template (.docx)"

            uploaded_template = st.file_uploader(
                upload_label, type=allowed_types, key="template_uploader"
            )

            tags = st.text_input("🏷️ Add tags (comma-separated)", key="template_tags")
            if uploaded_template:
                try:
                    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    versioned_name = f"{timestamp}_{sanitize_filename(uploaded_template.name)}"
                    dropbox_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{versioned_name}"

                    # Upload directly to Dropbox
                    client.dbx.files_upload(
                        uploaded_template.getvalue(),
                        dropbox_path,
                        mode=WriteMode.overwrite
                    )

                    st.success(f"✅ Uploaded template: {versioned_name}")
                    clear_caches()

                    log_audit_event("Template Uploaded", {
                        "filename": versioned_name,
                        "tags": tags,
                        "category": selected_category,
                        "version": timestamp,
                        "module": "template_manager"
                    })

                    # Generate preview only for Word docs
                    if selected_category != "email":
                        local_path = client.download_file(dropbox_path, "templates_preview")
                        preview_path = local_path.replace(".docx", "_preview.docx")
                        replace_text_in_docx_all(local_path, {"Preview": "Sample"}, preview_path)
                        st.download_button(
                            "⬇️ Download Preview",
                            open(preview_path, "rb"),
                            file_name=os.path.basename(preview_path)
                        )

                except Exception as e:
                    msg = handle_error(e, code="TEMPLATE_UI_003")
                    st.error(msg)

            st.markdown("---")
            search_filter = st.text_input(
                "🔍 Search by name or tag", key="search_templates"
            ).lower()

            templates = get_templates(tenant_id=tenant_id, category=selected_category)
            matched_templates = [
                t for t in templates
                if search_filter in t.get("name", "").lower() or search_filter in (
                    "".join(json.loads(t.get("tags", "[]")))).lower()
            ]

            if matched_templates:
                for t in matched_templates:
                    name = t.get("name", "Unknown")
                    tags_raw = t.get("tags", "[]")
                    tags_list = json.loads(tags_raw) if tags_raw else []

                    col1, col2, col3 = st.columns([5, 2, 2])
                    with col1:
                        st.write(f"**{name}**")
                        if tags_list:
                            st.caption(f"🏷️ Tags: {', '.join(tags_list)}")

                        uploaded_at = t.get("uploaded_at")
                        if uploaded_at:
                            st.caption(f"📅 Uploaded: {uploaded_at.split('T')[0]}")

                    with col2:
                        new_name = st.text_input(
                            f"Rename {name}",
                            value=name.replace(".docx", ""),
                            key=f"rename_{name}"
                        )
                        if st.button("Rename", key=f"rename_btn_{name}"):
                            try:
                                old_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{name}"
                                new_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{sanitize_filename(new_name)}.docx"
                                client.dbx.files_move_v2(old_path, new_path, autorename=False)
                                st.success(f"✅ Renamed to {new_name}.docx")

                                clear_caches()
                                log_audit_event("Template Renamed", {
                                    "from": name,
                                    "to": f"{new_name}.docx"
                                })
                                st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_004")
                                st.error(msg)

                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_{name}"):
                            try:
                                dropbox_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{name}"
                                client.dbx.files_delete_v2(dropbox_path)
                                st.success(f"✅ Deleted {name}")

                                clear_caches()
                                log_audit_event("Template Deleted", {
                                    "filename": name,
                                    "category": selected_category
                                })
                                st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_005")
                                st.error(msg)
            else:
                st.info("No templates found matching your search.")

        except Exception as e:
            msg = handle_error(e, code="TEMPLATE_UI_006")
            st.error(msg)

    # ---------------- Tab 2 ----------------
    with tab2:
        try:
            selected_example_label = st.selectbox(
                "Choose Example Category", list(CATEGORIES.keys()), key="example_category"
            )
            example_category = CATEGORIES[selected_example_label]
            example_dir = os.path.join("examples", tenant_id, example_category)
            os.makedirs(example_dir, exist_ok=True)

            st.subheader(f"🖋️ {selected_example_label} Style Examples")

            uploaded_example = st.file_uploader(
                "Upload Style Example (.txt)", type=["txt"], key="example_uploader"
            )
            if uploaded_example:
                try:
                    example_path = os.path.join(example_dir, sanitize_filename(uploaded_example.name))
                    with open(example_path, "wb") as f:
                        f.write(uploaded_example.read())

                    meta = {
                        "filename": os.path.basename(example_path),
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "tenant_id": tenant_id,
                        "category": example_category,
                    }
                    with open(example_path.replace(".txt", ".json"), "w") as f:
                        json.dump(meta, f, indent=2)

                    st.success(f"✅ Uploaded example: {os.path.basename(example_path)}")

                    clear_caches()
                    log_audit_event("Style Example Uploaded", {
                        "filename": os.path.basename(example_path),
                        "tenant_id": tenant_id,
                        "category": example_category,
                        "module": "template_manager",
                    })

                except Exception as e:
                    msg = handle_error(e, code="TEMPLATE_UI_007")
                    st.error(msg)

            st.markdown("---")
            search_filter = st.text_input(
                "🔍 Search by name", key="search_examples"
            ).lower()

            examples = [f for f in os.listdir(example_dir) if f.endswith(".txt")]
            matched_examples = []
            for e in examples:
                meta_path = os.path.join(example_dir, e.replace(".txt", ".json"))
                meta = {}
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as mf:
                        meta = json.load(mf)
                if search_filter in e.lower():
                    matched_examples.append((e, meta.get("uploaded_at")))

            if matched_examples:
                for filename, uploaded_at in matched_examples:
                    col1, col2, col3 = st.columns([5, 2, 2])
                    with col1:
                        st.write(f"🖋️ **{filename}**")
                        if uploaded_at:
                            st.caption(f"📅 Uploaded: {uploaded_at.split('T')[0]}")

                    example_path = os.path.join(example_dir, filename)
                    meta_path = example_path.replace(".txt", ".json")

                    with col2:
                        new_name = st.text_input(
                            f"Rename {filename}",
                            value=filename.replace(".txt", ""),
                            key=f"rename_ex_{filename}"
                        )
                        if st.button("Rename", key=f"rename_ex_btn_{filename}"):
                            try:
                                new_path = os.path.join(example_dir, sanitize_filename(new_name) + ".txt")
                                if os.path.exists(new_path):
                                    st.warning("⚠️ File with that name already exists.")
                                else:
                                    os.rename(example_path, new_path)
                                    try:
                                        os.rename(meta_path, new_path.replace(".txt", ".json"))
                                    except:
                                        pass
                                    st.success(f"✅ Renamed to {new_name}.txt")

                                    clear_caches()
                                    log_audit_event("Style Example Renamed", {
                                        "from": filename,
                                        "to": f"{new_name}.txt",
                                        "tenant_id": tenant_id,
                                        "category": example_category,
                                        "module": "template_manager",
                                    })
                                    st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_008")
                                st.error(msg)

                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_ex_{filename}"):
                            try:
                                os.remove(example_path)
                                try:
                                    os.remove(meta_path)
                                except:
                                    pass
                                st.success(f"✅ Deleted {filename}")

                                clear_caches()
                                log_audit_event("Style Example Deleted", {
                                    "filename": filename,
                                    "tenant_id": tenant_id,
                                    "category": example_category,
                                    "module": "template_manager",
                                })
                                st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_009")
                                st.error(msg)
            else:
                st.info("No examples found matching your search.")

        except Exception as e:
            msg = handle_error(e, code="TEMPLATE_UI_010")
            st.error(msg)

    # ---------------- Tab 3 ----------------
    with tab3:
        try:
            st.subheader("🎨 Tenant Branding Assets")
            branding_dir = os.path.join("branding", tenant_id, "assets")
            os.makedirs(branding_dir, exist_ok=True)

            logo_upload = st.file_uploader("Upload Firm Logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="branding_logo")
            primary_color = st.color_picker("Pick Primary Color", value=branding.get("primary_color", "#0A1D3B"))

            branding_config_path = os.path.join(branding_dir, "branding.json")

            if logo_upload:
                logo_path = os.path.join(branding_dir, sanitize_filename(logo_upload.name))
                with open(logo_path, "wb") as f:
                    f.write(logo_upload.read())
                branding["logo"] = logo_path
                branding["primary_color"] = primary_color
                with open(branding_config_path, "w") as f:
                    json.dump(branding, f, indent=2)
                st.success("✅ Branding updated successfully.")
                log_audit_event("Branding Updated", {
                    "tenant_id": tenant_id,
                    "logo": logo_path,
                    "color": primary_color
                })

        except Exception as e:
            msg = handle_error(e, code="TEMPLATE_UI_011")
            st.error(msg)
