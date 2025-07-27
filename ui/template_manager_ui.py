import streamlit as st
import os
import json
from datetime import datetime

from core.auth import get_tenant_id, get_user_id
from core.security import sanitize_filename, redact_log, mask_phi
from core.audit import log_audit_event
from core.cache_utils import clear_caches
from core.error_handling import handle_error
from logger import logger
from core.db import insert_template, get_templates, soft_delete_template, update_template_name, insert_audit_event


CATEGORIES = {
    "Mediation Memo": "mediation",
    "Demand Letter": "demand",
    "FOIA Letter": "foia",
    "Batch Documents": "batch_docs"
}


def get_dir(base_dir: str, tenant_id: str, category: str) -> str:
    try:
        path = os.path.join(base_dir, tenant_id, category)
        os.makedirs(path, exist_ok=True)
        return path
    except Exception as e:
        msg = handle_error(e, code="TEMPLATE_UI_001")
        st.error(msg)
        return ""


def run_ui():
    st.header("📪 Template & Style Example Manager")

    try:
        tenant_id = get_tenant_id()
    except Exception as e:
        msg = handle_error(e, code="TEMPLATE_UI_002")
        st.error(msg)
        return

    tab1, tab2 = st.tabs(["📂 Templates", "🖋️ Style Examples"])

    with tab1:
        try:
            selected_category_label = st.selectbox(
                "Choose Template Category", list(CATEGORIES.keys()), key="template_category"
            )
            selected_category = CATEGORIES[selected_category_label]
            template_dir = get_dir("templates", tenant_id, selected_category)

            st.subheader(f"📁 {selected_category_label} Templates")

            uploaded_template = st.file_uploader(
                "Upload Template (.docx)", type=["docx"], key="template_uploader"
            )
            tags = st.text_input("🏷️ Add tags (comma-separated)", key="template_tags")
            if uploaded_template:
                try:
                    template_path = os.path.join(template_dir, sanitize_filename(uploaded_template.name))
                    with open(template_path, "wb") as f:
                        f.write(uploaded_template.read())

                    # DB Insert
                    insert_template(
                        tenant_id=tenant_id,
                        name=os.path.basename(template_path),
                        path=template_path,
                        category=selected_category,
                        tags=[t.strip() for t in tags.split(",") if t.strip()]
                    )

                    st.success(f"✅ Uploaded template: {os.path.basename(template_path)}")

                    clear_caches()

                    # DB Audit
                    insert_audit_event(
                        tenant_id=tenant_id,
                        user_id=get_user_id(),
                        action="Template Uploaded",
                        metadata={
                            "filename": os.path.basename(template_path),
                            "tags": tags,
                            "category": selected_category,
                            "module": "template_manager"
                        }
                    )
                except Exception as e:
                    msg = handle_error(e, code="TEMPLATE_UI_003")
                    st.error(msg)

            st.markdown("---")
            search_filter = st.text_input(
                "🔍 Search by name or tag", key="search_templates"
            ).lower()

            # DB fetch
            templates = get_templates(tenant_id=tenant_id, category=selected_category)
            matched_templates = [
                t for t in templates
                if search_filter in t["name"].lower() or search_filter in (",".join(json.loads(t.get("tags", "[]")))).lower()
            ]

            if matched_templates:
                for t in matched_templates:
                    tags_list = json.loads(t.get("tags", "[]"))
                    col1, col2, col3 = st.columns([5, 2, 2])
                    with col1:
                        st.write(f"**{t['name']}**")
                        if tags_list:
                            st.caption(f"🏷️ Tags: {', '.join(tags_list)}")
                        if t["uploaded_at"]:
                            st.caption(f"📅 Uploaded: {t['uploaded_at'].split('T')[0]}")

                    with col2:
                        new_name = st.text_input(
                            f"Rename {t['name']}",
                            value=t['name'].replace(".docx", ""),
                            key=f"rename_{t['id']}",
                        )
                        if st.button("Rename", key=f"rename_btn_{t['id']}"):
                            try:
                                new_path = os.path.join(template_dir, sanitize_filename(new_name) + ".docx")
                                if os.path.exists(new_path):
                                    st.warning("⚠️ File with that name already exists.")
                                else:
                                    os.rename(t["path"], new_path)
                                    # DB Update
                                    update_template_name(t["id"], tenant_id, new_name + ".docx", new_path)
                                    st.success(f"✅ Renamed to {new_name}.docx")

                                    clear_caches()

                                    insert_audit_event(
                                        tenant_id=tenant_id,
                                        user_id=get_user_id(),
                                        action="Template Renamed",
                                        metadata={"from": t["name"], "to": new_name + ".docx"}
                                    )
                                    st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_004")
                                st.error(msg)

                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_{t['id']}"):
                            try:
                                # DB Soft Delete
                                soft_delete_template(t["id"], tenant_id)
                                if os.path.exists(t["path"]):
                                    os.remove(t["path"])
                                st.success(f"✅ Deleted {t['name']}")

                                clear_caches()

                                insert_audit_event(
                                    tenant_id=tenant_id,
                                    user_id=get_user_id(),
                                    action="Template Deleted",
                                    metadata={"filename": t["name"], "category": selected_category}
                                )
                                st.rerun()
                            except Exception as e:
                                msg = handle_error(e, code="TEMPLATE_UI_005")
                                st.error(msg)
            else:
                st.info("No templates found matching your search.")

        except Exception as e:
            msg = handle_error(e, code="TEMPLATE_UI_006")
            st.error(msg)

    # Style Examples Tab (still uses file system for now)
    with tab2:
        try:
            selected_example_label = st.selectbox(
                "Choose Example Category", list(CATEGORIES.keys()), key="example_category"
            )
            example_category = CATEGORIES[selected_example_label]
            example_dir = get_dir("examples", tenant_id, example_category)

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

                    try:
                        log_audit_event("Style Example Uploaded", {
                            "filename": os.path.basename(example_path),
                            "tenant_id": tenant_id,
                            "category": example_category,
                            "module": "template_manager",
                        })
                    except Exception as e:
                        logger.warning(redact_log(mask_phi(f"⚠️ Failed to write audit log: {e}")))
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
                            key=f"rename_ex_{filename}",
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
                                        "to": new_name + ".txt",
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
