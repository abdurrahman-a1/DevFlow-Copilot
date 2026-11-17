import json
import requests
import streamlit as st

API_BASE_URL = "http://127.0.0.1:8000/api/v1"

st.set_page_config(page_title="MoinSystems AI DevFlow Copilot", layout="wide")
st.title("MoinSystems AI DevFlow Copilot")
st.caption("Day 1 Milestone — Local Text-to-Structured-Requirement Pipeline")

# Check FastAPI + Model status in sidebar
with st.sidebar:
    st.header("System Status")
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=3).json()
        st.success("Backend Connected")
        st.write(f"**Model:** `{health['model']}`")
        st.write(f"**Prompt:** `{health['prompt_version']}`")
    except Exception:
        st.error("FastAPI backend offline. Start uvicorn first.")

# Input Section
project_name = st.text_input("Project Name", placeholder="e.g., Clinic Appointment Portal")
raw_text = st.text_area(
    "Client Requirements / Meeting Notes",
    height=200,
    placeholder="Paste messy client requirements, email briefs, or meeting notes here...",
)

if st.button("Generate Specification", type="primary"):
    if not project_name.strip() or not raw_text.strip():
        st.warning("Please provide both a Project Name and Client Requirements.")
    else:
        with st.spinner("Generating structured specification locally via Ollama..."):
            try:
                res = requests.post(
                    f"{API_BASE_URL}/generate",
                    json={"project_name": project_name, "raw_text": raw_text},
                    timeout=180,
                )
                if res.status_code == 200:
                    st.session_state["last_result"] = res.json()
                else:
                    detail = res.json().get("detail", res.text)
                    st.error(f"Generation Failed ({res.status_code}): {detail}")
            except Exception as exc:
                st.error(f"Request error: {exc}")

# Display Results
if "last_result" in st.session_state:
    result = st.session_state["last_result"]
    spec = result["specification"]

    st.warning("AI-generated draft - requires human review")
    st.info(
        f"Run ID: `{result['run_id']}` | Artifact ID: `{result['artifact_id']}` | "
        f"Model: `{result['model_name']}` | Prompt: `{result['prompt_version']}` | "
        f"Status: `{result['review_status'].upper()}`"
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Summary & Features", "User Stories", "Assumptions & Open Questions", "Raw JSON"]
    )

    with tab1:
        st.subheader("Project Summary")
        st.write(spec["project_summary"])
        st.subheader("Extracted Features")
        if spec["features"]:
            for feat in spec["features"]:
                st.markdown(f"- **{feat['name']}** (`{feat['priority']}`): {feat['description']}")
        else:
            st.write("No explicit features extracted.")

    with tab2:
        st.subheader("User Stories")
        if spec["user_stories"]:
            for idx, story in enumerate(spec["user_stories"], 1):
                st.markdown(
                    f"**US-{idx:03d}:** As a **{story['role']}**, I want to **{story['goal']}**, "
                    f"so that **{story['benefit']}**."
                )
        else:
            st.write("No user stories generated.")

    with tab3:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Assumptions (Inferred)")
            for item in spec["assumptions"]:
                st.markdown(f"- {item}")
        with col2:
            st.subheader("Open Questions (Missing Info)")
            for q in spec["open_questions"]:
                st.markdown(f"- {q}")

    with tab4:
        st.code(json.dumps(spec, indent=2), language="json")