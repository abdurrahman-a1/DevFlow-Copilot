import json
import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(page_title="MoinSystems AI DevFlow Copilot", layout="wide")
st.title("MoinSystems AI DevFlow Copilot")
st.caption("Local-First Software-House GenAI Product — Integrated MVP")

# --- Sidebar: System Status, Navigation & Project History ---
with st.sidebar:
    st.header("System Status")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=3).json()
        st.success("FastAPI + Ollama Ready")
        st.write(f"**Spec Model:** `{health['model']}`")
        st.write(f"**Vision Model:** `{health['vision_model']}`")
        st.write(f"**Active Prompt:** `{health['prompt_version']}`")
    except Exception:
        st.error("FastAPI backend offline. Start uvicorn first.")

    st.divider()
    nav_page = st.radio("Navigation", ["Project Workspace", "Evaluation Dashboard"])

    st.divider()
    st.subheader("Project Run History")
    try:
        hist_res = requests.get(f"{API_BASE_URL}/projects", timeout=5).json()
        runs_list = hist_res.get("runs", [])
        if runs_list:
            options = {
                f"Run #{r['run_id']} — {r['project_name']} [{r['review_status'].upper()}]": r["run_id"]
                for r in runs_list
            }
            selected_label = st.selectbox("Load Existing Run", ["+ New Project"] + list(options.keys()))
            if selected_label != "+ New Project":
                chosen_run_id = options[selected_label]
                if st.button("Load Selected Run"):
                    detail = requests.get(f"{API_BASE_URL}/runs/{chosen_run_id}", timeout=10).json()
                    st.session_state["active_run"] = detail
        else:
            st.caption("No saved runs yet.")
    except Exception:
        st.caption("History unavailable while offline.")

# ==========================================
# PAGE 1: PROJECT WORKSPACE
# ==========================================
if nav_page == "Project Workspace":
    with st.expander("Create New Project Generation Run", expanded=("active_run" not in st.session_state)):
        project_name = st.text_input("Project Name", placeholder="e.g., Client Billing & Invoice Portal")
        input_mode = st.radio(
            "Input Mode",
            ["Text Only", "Image / Screenshot Only", "Combined (Text + Screenshot)"],
            horizontal=True,
        )

        raw_text = ""
        uploaded_file = None

        if input_mode in ("Text Only", "Combined (Text + Screenshot)"):
            raw_text = st.text_area(
                "Client Requirements / Meeting Notes",
                height=140,
                placeholder="Paste unstructured client requirements or meeting notes...",
            )

        if input_mode in ("Image / Screenshot Only", "Combined (Text + Screenshot)"):
            uploaded_file = st.file_uploader(
                "Upload Screenshot / Wireframe (PNG, JPG, WEBP - max 5MB)",
                type=["png", "jpg", "jpeg", "webp"],
            )
            if uploaded_file is not None:
                st.image(uploaded_file, caption="Uploaded Screenshot Preview", width=400)

        if st.button("Generate Structured Specification", type="primary"):
            if not project_name.strip():
                st.warning("Please enter a Project Name.")
            else:
                with st.spinner("Running local Ollama pipeline..."):
                    try:
                        form_data = {"project_name": project_name.strip(), "raw_text": raw_text.strip()}
                        files = None
                        if uploaded_file is not None:
                            files = {
                                "image": (
                                    uploaded_file.name,
                                    uploaded_file.getvalue(),
                                    uploaded_file.type or "image/png",
                                )
                            }
                        res = requests.post(
                            f"{API_BASE_URL}/generate-multimodal",
                            data=form_data,
                            files=files,
                            timeout=300,
                        )
                        if res.status_code == 200:
                            created = res.json()
                            detail = requests.get(f"{API_BASE_URL}/runs/{created['run_id']}", timeout=10).json()
                            detail["image_evidence"] = created.get("image_evidence")
                            st.session_state["active_run"] = detail
                            st.rerun()
                        else:
                            st.error(f"Generation Failed ({res.status_code}): {res.json().get('detail', res.text)}")
                    except Exception as exc:
                        st.error(f"Request error: {exc}")

    if "active_run" in st.session_state:
        run_data = st.session_state["active_run"]
        run_id = run_data["run_id"]
        artifact_id = run_data["artifact_id"]
        status = run_data["review_status"]
        spec = run_data["specification"]
        eng_bundle = run_data.get("engineering_artifacts")

        st.divider()
        if status in ("approved", "edited"):
            st.success(f"REVIEW STATUS: {status.upper()} — Ready for Export")
        elif status == "rejected":
            st.error("REVIEW STATUS: REJECTED — Needs Regeneration")
        else:
            st.warning("AI-generated draft - requires human review")

        st.info(
            f"**Project:** {run_data['project_name']} | **Run ID:** `{run_id}` | "
            f"**Source:** `{run_data['input_type'].upper()}` | **Model:** `{run_data['model_name']}` | "
            f"**Prompt:** `{run_data['prompt_version']}`"
        )

        # Action Bar: Generate Artifacts + Human-Gated Exports
        c_art, c_md, c_json = st.columns([2, 1, 1])
        with c_art:
            if st.button("Generate / Refresh Developer & QA Artifacts"):
                with st.spinner("Generating Acceptance Criteria, Plan, QA Tests, Dev Prompt, Client Update & Release Notes..."):
                    art_res = requests.post(f"{API_BASE_URL}/runs/{run_id}/artifacts", timeout=360)
                    if art_res.status_code == 200:
                        refreshed = requests.get(f"{API_BASE_URL}/runs/{run_id}", timeout=10).json()
                        st.session_state["active_run"] = refreshed
                        st.rerun()
                    else:
                        st.error(f"Failed: {art_res.json().get('detail', art_res.text)}")

        is_approved = status in ("approved", "edited")
        with c_md:
            if is_approved:
                md_resp = requests.get(f"{API_BASE_URL}/runs/{run_id}/export?format=markdown", timeout=15)
                if md_resp.status_code == 200:
                    st.download_button(
                        "Export Approved Markdown",
                        data=md_resp.text,
                        file_name=f"devflow_run_{run_id}_approved.md",
                        mime="text/markdown",
                    )
            else:
                st.button("Export Markdown (Approve First)", disabled=True)

        with c_json:
            if is_approved:
                json_resp = requests.get(f"{API_BASE_URL}/runs/{run_id}/export?format=json", timeout=15)
                if json_resp.status_code == 200:
                    st.download_button(
                        "Export Approved JSON",
                        data=json_resp.text,
                        file_name=f"devflow_run_{run_id}_approved.json",
                        mime="application/json",
                    )
            else:
                st.button("Export JSON (Approve First)", disabled=True)

        # Artifact Tabs
        tabs = st.tabs(
            [
                "Specification",
                "User Stories",
                "Observed vs. Assumed",
                "Acceptance Criteria",
                "Implementation Plan",
                "QA Test Cases",
                "Developer Prompt",
                "Client Update & Release Notes",
                "Human Review Gate",
            ]
        )

        with tabs[0]:
            st.subheader("Project Summary")
            st.write(spec.get("project_summary", ""))
            st.subheader("Features")
            for feat in spec.get("features", []):
                st.markdown(f"- **{feat['name']}** (`{feat['priority']}`): {feat['description']}")

        with tabs[1]:
            st.subheader("User Stories")
            for idx, us in enumerate(spec.get("user_stories", []), 1):
                st.markdown(f"**US-{idx:03d}:** As a **{us['role']}**, I want to **{us['goal']}**, so that **{us['benefit']}**.")

        with tabs[2]:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.subheader("Observed Evidence")
                for ev in spec.get("evidence_notes", []):
                    st.markdown(f"- {ev}")
            with col2:
                st.subheader("Assumptions")
                for item in spec.get("assumptions", []):
                    st.markdown(f"- {item}")
            with col3:
                st.subheader("Open Questions")
                for q in spec.get("open_questions", []):
                    st.markdown(f"- {q}")

        with tabs[3]:
            if eng_bundle and eng_bundle.get("acceptance_criteria"):
                for ac in eng_bundle["acceptance_criteria"]:
                    st.markdown(f"- **{ac['story_id']}:** **Given** {ac['given']}, **When** {ac['when']}, **Then** {ac['then']}.")
            else:
                st.info("Click 'Generate / Refresh Developer & QA Artifacts' above to populate.")

        with tabs[4]:
            if eng_bundle and eng_bundle.get("implementation_plan"):
                plan = eng_bundle["implementation_plan"]
                for sec in ["frontend", "backend", "data", "apis", "dependencies", "risks"]:
                    st.subheader(sec.capitalize())
                    for entry in plan.get(sec, []):
                        st.markdown(f"- {entry}")
            else:
                st.info("Generate engineering artifacts above to view the Implementation Plan.")

        with tabs[5]:
            if eng_bundle and eng_bundle.get("qa_test_cases"):
                for tc in eng_bundle["qa_test_cases"]:
                    st.markdown(f"**{tc['test_id']}** [`{tc['category'].upper()}`] — **{tc['title']}**")
                    st.markdown(f"- Steps: {' -> '.join(tc['steps'])} | Expected: {tc['expected_result']}")
            else:
                st.info("Generate engineering artifacts above to view QA Test Cases.")

        with tabs[6]:
            if eng_bundle and eng_bundle.get("developer_prompt"):
                st.code(eng_bundle["developer_prompt"], language="text")
            else:
                st.info("Generate engineering artifacts above to view the Developer Prompt.")

        with tabs[7]:
            if eng_bundle:
                st.subheader("Client Progress Update")
                st.write(eng_bundle.get("client_update", ""))
                st.divider()
                st.subheader("Draft Release Notes")
                st.write(eng_bundle.get("release_notes", ""))
            else:
                st.info("Generate engineering artifacts above to view Client Update & Release Notes.")

        with tabs[8]:
            st.subheader("Mandatory Human Review Gate")
            reviewer_note = st.text_input("Reviewer Note / Sign-off Comment", placeholder="e.g., Verified features against client brief.")

            r_col1, r_col2 = st.columns(2)
            with r_col1:
                if st.button("Approve Artifacts", type="primary"):
                    resp = requests.post(
                        f"{API_BASE_URL}/artifacts/{artifact_id}/review",
                        json={"action": "approved", "reviewer_note": reviewer_note},
                    )
                    if resp.status_code == 200:
                        st.session_state["active_run"] = requests.get(f"{API_BASE_URL}/runs/{run_id}").json()
                        st.rerun()

            with r_col2:
                if st.button("Reject Draft"):
                    resp = requests.post(
                        f"{API_BASE_URL}/artifacts/{artifact_id}/review",
                        json={"action": "rejected", "reviewer_note": reviewer_note or "Rejected by reviewer"},
                    )
                    if resp.status_code == 200:
                        st.session_state["active_run"] = requests.get(f"{API_BASE_URL}/runs/{run_id}").json()
                        st.rerun()

            st.divider()
            st.subheader("Edit Specification JSON Directly")
            edited_spec_str = st.text_area("Edit JSON (validated against Pydantic schema on save)", value=json.dumps(spec, indent=2), height=240)
            if st.button("Save Edited Specification & Approve"):
                resp = requests.post(
                    f"{API_BASE_URL}/artifacts/{artifact_id}/review",
                    json={"action": "edited", "reviewer_note": reviewer_note or "Edited by reviewer", "edited_json": edited_spec_str},
                )
                if resp.status_code == 200:
                    st.session_state["active_run"] = requests.get(f"{API_BASE_URL}/runs/{run_id}").json()
                    st.rerun()
                else:
                    st.error(f"Edit validation error: {resp.json().get('detail', resp.text)}")

            st.divider()
            st.subheader("Regenerate with Reviewer Feedback")
            regen_feedback = st.text_area("What should the model fix or clarify in the next run?", placeholder="e.g., Add role-based access control for managers and flag payment gateway as an open question.")
            if st.button("Regenerate Run"):
                if not regen_feedback.strip():
                    st.warning("Enter feedback instructions first.")
                else:
                    with st.spinner("Regenerating specification with reviewer feedback..."):
                        reg_res = requests.post(
                            f"{API_BASE_URL}/runs/{run_id}/regenerate",
                            json={"reviewer_feedback": regen_feedback},
                            timeout=300,
                        )
                        if reg_res.status_code == 200:
                            new_run_id = reg_res.json()["run_id"]
                            st.session_state["active_run"] = requests.get(f"{API_BASE_URL}/runs/{new_run_id}").json()
                            st.rerun()

            if run_data.get("review_history"):
                st.subheader("Audit Trail")
                for fb in run_data["review_history"]:
                    st.markdown(f"- **{fb['label'].upper()}** ({fb['created_at']}): {fb.get('reviewer_note') or 'No note'}")

# ==========================================
# PAGE 2: EVALUATION DASHBOARD
# ==========================================
else:
    st.header("GenAI Evaluation & Reliability Dashboard")
    try:
        eval_data = requests.get(f"{API_BASE_URL}/evaluation/summary", timeout=5).json()
        if eval_data.get("total_records", 0) == 0:
            st.info("No evaluation records found in SQLite yet. Run `python -m eval.run_evaluation` to populate the 30-scenario benchmark.")
        else:
            st.write(f"**Total Logged Evaluation Runs:** `{eval_data['total_records']}`")
            cols = st.columns(len(eval_data["by_prompt"]))
            for idx, (pv, metrics) in enumerate(eval_data["by_prompt"].items()):
                with cols[idx]:
                    st.subheader(f"Prompt: `{pv}`")
                    st.metric("Overall Quality Score", f"{metrics['avg_overall']} / 5.0")
                    st.metric("Schema Pass Rate", f"{metrics['pass_rate_pct']}%")
                    st.write(f"- Completeness: `{metrics['avg_completeness']}/5`")
                    st.write(f"- Evidence Fidelity: `{metrics['avg_evidence_fidelity']}/5`")
                    st.write(f"- Uncertainty Handling: `{metrics['avg_uncertainty']}/5`")
                    st.write(f"- Engineering Usefulness: `{metrics['avg_usefulness']}/5`")
    except Exception as exc:
        st.error(f"Could not load evaluation summary: {exc}")