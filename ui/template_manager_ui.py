import streamlit as st
import os
import json
from datetime import datetime

from core.auth import get_tenant_id, get_user_role, get_tenant_branding
from utils.file_utils import sanitize_filename
from core.audit import log_audit_event
from core.cache_utils import clear_caches
from core.error_handling import handle_error
from logger import logger
from core.db import get_templates
from utils.docx_utils import replace_text_in_docx_all
from services.dropbox_client import DropboxClient
from core.constants import DROPBOX_TEMPLATES_ROOT
from dropbox.files import WriteMode

# Template categories available
CATEGORIES = {
    "Mediation Memo": "mediation",
    "Demand Letter": "demand",
    "FOIA Letter": "foia",
    "Batch Documents": "batch_docs",
    "Email Templates": "email"
}

def normalize_filename(name: str, category: str) -> str:
    """
    Normalize a file name by removing duplicate extensions and ensuring the right extension.
    """
    name = os.path.basename(name)
    name = sanitize_filename(name)

    # Remove duplicate extensions (loops until fixed)
    while name.endswith((".txt.txt", ".docx.docx", ".docx.txt", ".txt.docx")):
        if ".txt" in name:
            name = name.rsplit(".", 1)[0] + ".txt"
        else:
            name = name.rsplit(".", 1)[0] + ".docx"

    # Ensure proper extension
    if category == "email" and not name.endswith(".txt"):
        name = f"{os.path.splitext(name)[0]}.txt"
    elif category != "email" and not name.endswith(".docx"):
        name = f"{os.path.splitext(name)[0]}.docx"

    return name


def run_ui():
    st.header("📪 Template & Style Example Manager")

    # Tenant info
    try:
        tenant_id = get_tenant_id()
        branding = get_tenant_branding(tenant_id)
        st.caption(f"Tenant: {branding.get('firm_name', tenant_id)}")
    except Exception as e:
        st.error(handle_error(e, code="TEMPLATE_UI_002"))
        return

    if get_user_role() != "admin":
        st.warning("⚠️ Only Admins can manage templates.")
        return

    tab1, tab2, tab3 = st.tabs(["📂 Templates", "🖋️ Style Examples", "🎨 Branding"])
    client = DropboxClient()

    # ==================== Tab 1: Templates ==================== #
    with tab1:
        try:
            selected_category_label = st.selectbox(
                "Choose Template Category", list(CATEGORIES.keys()), key="template_category"
            )
            selected_category = CATEGORIES[selected_category_label]

            st.subheader(f"📁 {selected_category_label} Templates")

            allowed_types = ["txt"] if selected_category == "email" else ["docx"]
            upload_label = "Upload Template (.txt)" if selected_category == "email" else "Upload Template (.docx)"

            uploaded_template = st.file_uploader(upload_label, type=allowed_types)
            tags = st.text_input("🏷️ Add tags (comma-separated)")

            # Upload new template
            if uploaded_template:
                try:
                    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    normalized_name = normalize_filename(uploaded_template.name, selected_category)
                    versioned_name = f"{timestamp}_{normalized_name}"

                    dropbox_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{versioned_name}"
                    client.dbx.files_upload(uploaded_template.getvalue(), dropbox_path, mode=WriteMode.overwrite)

                    st.success(f"✅ Uploaded template: {versioned_name}")
                    clear_caches()

                    log_audit_event("Template Uploaded", {
                        "filename": versioned_name,
                        "tags": tags,
                        "category": selected_category,
                        "version": timestamp,
                        "module": "template_manager"
                    })

                    # Generate preview for Word templates
                    if selected_category != "email":
                        local_path = client.download_file(dropbox_path, "templates_preview")
                        preview_path = local_path.replace(".docx", "_preview.docx")
                        replace_text_in_docx_all(local_path, {"Preview": "Sample"}, preview_path)
                        st.download_button(
                            "⬇️ Download Preview", open(preview_path, "rb"), file_name=os.path.basename(preview_path)
                        )
                except Exception as e:
                    st.error(handle_error(e, code="TEMPLATE_UI_003"))

            st.markdown("---")
            search_filter = st.text_input("🔍 Search by name or tag").lower()

            # Load template list
            templates = get_templates(tenant_id=tenant_id, category=selected_category)
            matched_templates = [
                t for t in templates
                if search_filter in t.get("name", "").lower() or
                search_filter in "".join(json.loads(t.get("tags", "[]"))).lower()
            ]

            if matched_templates:
                for t in matched_templates:
                    name = t.get("name", "Unknown")
                    tags_list = json.loads(t.get("tags", "[]") or "[]")
                    uploaded_at = t.get("uploaded_at", "")

                    col1, col2, col3 = st.columns([5, 2, 2])
                    with col1:
                        st.write(f"**{name}**")
                        if tags_list:
                            st.caption(f"🏷️ Tags: {', '.join(tags_list)}")
                        if uploaded_at:
                            st.caption(f"📅 Uploaded: {uploaded_at.split('T')[0]}")

                    with col2:
                        new_name = st.text_input(
                            f"Rename {name}", value=name.rsplit(".", 1)[0], key=f"rename_{name}"
                        )
                        if st.button("Rename", key=f"rename_btn_{name}"):
                            try:
                                clean_new_name = normalize_filename(new_name, selected_category)
                                old_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{name}"
                                new_path = f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{clean_new_name}"

                                client.dbx.files_move_v2(old_path, new_path, autorename=False)
                                st.success(f"✅ Renamed to {clean_new_name}")
                                clear_caches()

                                log_audit_event("Template Renamed", {"from": name, "to": clean_new_name})
                                st.rerun()
                            except Exception as e:
                                st.error(handle_error(e, code="TEMPLATE_UI_004"))

                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_{name}"):
                            try:
                                client.dbx.files_delete_v2(f"{DROPBOX_TEMPLATES_ROOT}/{selected_category}/{name}")
                                st.success(f"✅ Deleted {name}")
                                clear_caches()

                                log_audit_event("Template Deleted", {
                                    "filename": name, "category": selected_category
                                })
                                st.rerun()
                            except Exception as e:
                                st.error(handle_error(e, code="TEMPLATE_UI_005"))
            else:
                st.info("No templates found matching your search.")

        except Exception as e:
            st.error(handle_error(e, code="TEMPLATE_UI_006"))

    # ==================== Tab 2: Style Examples ==================== #
    with tab2:
        try:
            selected_example_label = st.selectbox(
                "Choose Example Category", list(CATEGORIES.keys()), key="example_category"
            )
            example_category = CATEGORIES[selected_example_label]
            example_dir = os.path.join("examples", tenant_id, example_category)
            os.makedirs(example_dir, exist_ok=True)

            st.subheader(f"🖋️ {selected_example_label} Style Examples")

            uploaded_example = st.file_uploader("Upload Style Example (.txt)", type=["txt"])
            if uploaded_example:
                try:
                    normalized_name = normalize_filename(uploaded_example.name, "email")
                    example_path = os.path.join(example_dir, normalized_name)

                    with open(example_path, "wb") as f:
                        f.write(uploaded_example.read())

                    meta = {
                        "filename": normalized_name,
                        "uploaded_at": datetime.utcnow().isoformat(),
                        "tenant_id": tenant_id,
                        "category": example_category,
                    }
                    with open(example_path.replace(".txt", ".json"), "w") as f:
                        json.dump(meta, f, indent=2)

                    st.success(f"✅ Uploaded example: {normalized_name}")
                    clear_caches()

                    log_audit_event("Style Example Uploaded", {
                        "filename": normalized_name,
                        "tenant_id": tenant_id,
                        "category": example_category,
                        "module": "template_manager"
                    })
                except Exception as e:
                    st.error(handle_error(e, code="TEMPLATE_UI_007"))

            st.markdown("---")
            search_filter = st.text_input("🔍 Search by name").lower()
            examples = [f for f in os.listdir(example_dir) if f.endswith(".txt")]

            if examples:
                for filename in examples:
                    meta_path = os.path.join(example_dir, filename.replace(".txt", ".json"))
                    uploaded_at = ""
                    if os.path.exists(meta_path):
                        with open(meta_path, "r") as mf:
                            meta = json.load(mf)
                            uploaded_at = meta.get("uploaded_at", "")

                    if search_filter not in filename.lower():
                        continue

                    col1, col2, col3 = st.columns([5, 2, 2])
                    with col1:
                        st.write(f"🖋️ **{filename}**")
                        if uploaded_at:
                            st.caption(f"📅 Uploaded: {uploaded_at.split('T')[0]}")

                    with col2:
                        new_name = st.text_input(
                            f"Rename {filename}", value=filename.replace(".txt", ""), key=f"rename_ex_{filename}"
                        )
                        if st.button("Rename", key=f"rename_ex_btn_{filename}"):
                            try:
                                clean_new_name = normalize_filename(new_name, "email")
                                new_path = os.path.join(example_dir, clean_new_name)

                                if os.path.exists(new_path):
                                    st.warning("⚠️ File with that name already exists.")
                                else:
                                    os.rename(example_dir + "/" + filename, new_path)
                                    if os.path.exists(meta_path):
                                        os.rename(meta_path, new_path.replace(".txt", ".json"))

                                    st.success(f"✅ Renamed to {clean_new_name}")
                                    clear_caches()
                                    log_audit_event("Style Example Renamed", {
                                        "from": filename,
                                        "to": clean_new_name,
                                        "tenant_id": tenant_id,
                                        "category": example_category,
                                        "module": "template_manager"
                                    })
                                    st.rerun()
                            except Exception as e:
                                st.error(handle_error(e, code="TEMPLATE_UI_008"))

                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_ex_{filename}"):
                            try:
                                os.remove(example_dir + "/" + filename)
                                if os.path.exists(meta_path):
                                    os.remove(meta_path)

                                st.success(f"✅ Deleted {filename}")
                                clear_caches()
                                log_audit_event("Style Example Deleted", {
                                    "filename": filename,
                                    "tenant_id": tenant_id,
                                    "category": example_category,
                                    "module": "template_manager"
                                })
                                st.rerun()
                            except Exception as e:
                                st.error(handle_error(e, code="TEMPLATE_UI_009"))
            else:
                st.info("No examples found matching your search.")

        except Exception as e:
            st.error(handle_error(e, code="TEMPLATE_UI_010"))

    # ==================== Tab 3: Branding ==================== #
    with tab3:
        try:
            st.subheader("🎨 Tenant Branding Assets")
            branding_dir = os.path.join("branding", tenant_id, "assets")
            os.makedirs(branding_dir, exist_ok=True)

            logo_upload = st.file_uploader("Upload Firm Logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
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
            st.error(handle_error(e, code="TEMPLATE_UI_011"))
