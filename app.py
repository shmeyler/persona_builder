import streamlit as st
from openai import OpenAI
import os

# --- Load API key BEFORE using it ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("openai", {}).get("api_key", "")
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Stop if no key found ---
if not OPENAI_API_KEY:
    st.error("🚨 OpenAI API Key not found. Please set it in environment variables or Streamlit secrets.")
    st.stop()

# --- Page setup ---
st.set_page_config(page_title="🧠 Persona Builder", page_icon="🧠", layout="centered")
st.title("🧠 Persona Builder")
st.markdown("Create detailed marketing personas using AI. Fill out the form below.")

# --- Input Form ---
with st.form("persona_form"):
    st.subheader("🔍 Persona Details")

    persona_name = st.text_input("Persona Name")
    age_range = st.selectbox("Age Range", ["18-24", "25-34", "35-44", "45-54", "55+"])
    gender_identity = st.selectbox("Gender Identity", ["Male", "Female", "Nonbinary", "Prefer not to say"])
    location = st.text_input("Location (City, Region)")
    income_level = st.selectbox("Income Level", ["<$50K", "$50K-$100K", "$100K-$200K", ">$200K"])
    occupation = st.text_input("Occupation")
    education_level = st.selectbox("Education Level", ["High School", "Bachelor's", "Master's", "Doctorate"])
    interests = st.text_area("Core Interests (comma-separated)")
    pain_points = st.text_area("Challenges / Pain Points")
    goals = st.text_area("Goals / Motivations")
    media_channels = st.multiselect("Preferred Media Channels", ["Instagram", "TikTok", "LinkedIn", "YouTube", "Podcasts", "Facebook", "Twitter"])
    values = st.text_area("Values / Beliefs")

    submitted = st.form_submit_button("Generate Persona")

# --- When Form is Submitted ---
if submitted:
    if not persona_name:
        st.warning("Please enter a Persona Name before submitting.")
        st.stop()

    with st.spinner("🛠️ Generating persona..."):
        prompt = f"""
Create a detailed marketing persona based on the following attributes:

- Persona Name: {persona_name}
- Age Range: {age_range}
- Gender Identity: {gender_identity}
- Location: {location}
- Income Level: {income_level}
- Occupation: {occupation}
- Education Level: {education_level}
- Core Interests: {interests}
- Challenges and Pain Points: {pain_points}
- Goals and Motivations: {goals}
- Preferred Media Channels: {', '.join(media_channels)}
- Values and Beliefs: {values}

Format the response into these sections:
1. Summary
2. Behavioral Traits
3. Buying Motivations
4. Preferred Marketing Channels
5. Suggested Messaging Strategy
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert marketing strategist who creates detailed consumer personas."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1200
            )

            persona_output = response.choices[0].message.content
            st.success(f"🎯 Persona for {persona_name}")
            st.markdown(persona_output)

            st.download_button(
                label="📥 Download Persona",
                data=persona_output,
                file_name=f"{persona_name.replace(' ', '_').lower()}_persona.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error(f"⚠️ Error generating persona: {e}")
