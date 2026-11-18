import json
import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(page_title="MoinSystems AI DevFlow Copilot", layout="wide")
st.title("MoinSystems AI DevFlow Copilot")
st.caption("Day 3 Milestone — Multimodal Specification & Engineering Artifact Generator")

with st.sidebar:
    st.header("System Status")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=3).json()
        st.success("Backend Connected")
        st.write(f"**Spec Model:** `{health['model']}`")
        st.write(f"**Vision Model:** `{health['vision_model']}`")
        st.write(f"**Spec Prompt:** `{health['prompt_version']}`")
        st.write(f"**Artifact Prompts:** `{', '.join(health.get('artifacts_prompt_versions', []))}`")
    except Exception:
        st.error("FastAPI backend offline. Start uvicorn first.")

project_name = st.text_input("Project Name", placeholder="e.g., Customer Support Ticketing Portal")
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
        height=150,
        placeholder="Paste client requirements or meeting notes here...",
    )

if input_mode in ("Image / Screenshot Only", "Combined (Text + Screenshot)"):
    uploaded_file = st.file_uploader(
        "Upload UI Screenshot / Wireframe (PNG, JPG, WEBP - max 5MB)",
        type=["png", "jpg", "jpeg", "webp"],
    )
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Uploaded Screenshot Preview", width=420)

if st.button("1. Generate Structured Specification", type="primary"):
    if not project_name.strip():
        st.warning("Please provide a Project Name.")
    elif input_mode == "Text Only" and len(raw_text.strip()) < 10:
        st.warning("Please enter at least 10 characters of requirement text.")
    elif input_mode == "Image / Screenshot Only" and uploaded_file is None:
        st.warning("Please upload a screenshot or wireframe image.")
    elif input_mode == "Combined (Text + Screenshot)" and (len(raw_text.strip()) < 10 or uploaded_file is None):
        st.warning("Combined mode requires both requirement text (min 10 chars) and a screenshot.")
    else:
        with st.spinner("Generating specification locally via Ollama..."):
            try:
                form_data = {
                    "project_name": project_name.strip(),
                    "raw_text": raw_text.strip() if raw_text else "",
                }
                files = None
                if uploaded_file is not None:
                    files = {
                        "image": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "image/png")
                    }

                res = requests.post(
                    f"{API_BASE_URL}/generate-multimodal",
                    data=form_data,
                    files=files,
                    timeout=300,
                )
                if res.status_code == 200:
                    st.session_state["last_result"] = res.json()
                    st.session_state.pop("last_artifacts", None)
                else:
                    detail = res.json().get("detail", res.text)
                    st.error(f"Generation Failed ({res.status_code}): {detail}")
            except Exception as exc:
                st.error(f"Request error: {exc}")

if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    spec = result["specification"]
    img_ev = result.get("image_evidence")
    run_id = result["run_id"]

    st.warning("AI-generated draft - requires human review")
    st.info(
        f"Source Type: `{result['input_type'].upper()}` | Run ID: `{run_id}` | "
        f"Models: `{result['model_name']}` | Prompt: `{result['prompt_version']}` | "
        f"Status: `{result['review_status'].upper()}`"
    )

    col_gen, col_exp_md, col_exp_json = st.columns([2, 1, 1])
    with col_gen:
        if st.button("2. Generate Developer & QA Engineering Artifacts", type="secondary"):
            with st.spinner("Generating Acceptance Criteria, Plan, QA Tests, Dev Prompt, Client Update & Release Notes..."):
                try:
                    art_res = requests.post(f"{API_BASE_URL}/runs/{run_id}/artifacts", timeout=360)
                    if art_res.status_code == 200:
                        st.session_state["last_artifacts"] = art_res.json()
                    else:
                        detail = art_res.json().get("detail", art_res.text)
                        st.error(f"Artifact Generation Failed ({art_res.status_code}): {detail}")
                except Exception as exc:
                    st.error(f"Artifact request error: {exc}")

    with col_exp_md:
        try:
            md_resp = requests.get(f"{API_BASE_URL}/runs/{run_id}/export?format=markdown", timeout=15)
            if md_resp.status_code == 200:
                st.download_button(
                    "Export Markdown",
                    data=md_resp.text,
                    file_name=f"devflow_run_{run_id}.md",
                    mime="text/markdown",
                )
        except Exception:
            pass

    with col_exp_json:
        try:
            json_resp = requests.get(f"{API_BASE_URL}/runs/{run_id}/export?format=json", timeout=15)
            if json_resp.status_code == 200:
                st.download_button(
                    "Export JSON",
                    data=json_resp.text,
                    file_name=f"devflow_run_{run_id}.json",
                    mime="application/json",
                )
        except Exception:
            pass

    eng_bundle = st.session_state.get("last_artifacts", {}).get("artifacts")

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
        ]
    )

    with tabs[0]:
        st.subheader("Project Summary")
        st.write(spec["project_summary"])
        st.subheader("Extracted Features")
        for feat in spec["features"]:
            st.markdown(f"- **{feat['name']}** (`{feat['priority']}`): {feat['description']}")
        if img_ev:
            with st.expander("Raw Screenshot Evidence Details"):
                st.json(img_ev)

    with tabs[1]:
        st.subheader("User Stories")
        for idx, story in enumerate(spec["user_stories"], 1):
            st.markdown(
                f"**US-{idx:03d}:** As a **{story['role']}**, I want to **{story['goal']}**, "
                f"so that **{story['benefit']}**."
            )

    with tabs[2]:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("Observed Evidence")
            for ev in spec.get("evidence_notes", []):
                st.markdown(f"- {ev}")
        with c2:
            st.subheader("Assumptions (Inferred)")
            for item in spec["assumptions"]:
                st.markdown(f"- {item}")
        with c3:
            st.subheader("Open Questions (Absent Info)")
            for q in spec["open_questions"]:
                st.markdown(f"- {q}")

    with tabs[3]:
        if eng_bundle:
            st.subheader("Given / When / Then Acceptance Criteria")
            for ac in eng_bundle["acceptance_criteria"]:
                st.markdown(
                    f"- **{ac['story_id']}:** **Given** {ac['given']}, **When** {ac['when']}, **Then** {ac['then']}."
                )
        else:
            st.info("Click '2. Generate Developer & QA Engineering Artifacts' above to populate this tab.")

    with tabs[4]:
        if eng_bundle:
            plan = eng_bundle["implementation_plan"]
            for section in ["frontend", "backend", "data", "apis", "dependencies", "risks"]:
                st.subheader(section.capitalize())
                for entry in plan.get(section, []):
                    st.markdown(f"- {entry}")
        else:
            st.info("Generate engineering artifacts above to view the Implementation Plan.")

    with tabs[5]:
        if eng_bundle:
            st.subheader("QA Test Cases (Positive / Negative / Edge)")
            for tc in eng_bundle["qa_test_cases"]:
                st.markdown(f"**{tc['test_id']}** [`{tc['category'].upper()}`] — **{tc['title']}**")
                st.markdown(f"- **Steps:** {' -> '.join(tc['steps'])}")
                st.markdown(f"- **Expected:** {tc['expected_result']}")
        else:
            st.info("Generate engineering artifacts above to view QA Test Cases.")

    with tabs[6]:
        if eng_bundle:
            st.subheader("Context-Rich Developer Prompt")
            st.code(eng_bundle["developer_prompt"], language="text")
        else:
            st.info("Generate engineering artifacts above to view the Developer Prompt.")

    with tabs[7]:
        if eng_bundle:
            st.subheader("Client Progress Update")
            st.write(eng_bundle["client_update"])
            st.divider()
            st.subheader("Draft Release Notes")
            st.write(eng_bundle["release_notes"])
        else:
            st.info("Generate engineering artifacts above to view Client Update and Release Notes.")