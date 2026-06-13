import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import json
from openai import OpenAI

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="ExamMind AI | Student Wellness", layout="wide")

# Custom CSS for a clean, student-friendly look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4A90E2; color: white; }
    .status-box { padding: 20px; border-radius: 10px; margin-bottom: 10px; }
    .low-risk { background-color: #d4edda; color: #155724; }
    .med-risk { background-color: #fff3cd; color: #856404; }
    .high-risk { background-color: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_index=True)


# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('exammind.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, target_exam TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
                 id INTEGER PRIMARY KEY, 
                 username TEXT, 
                 mood_score INTEGER, 
                 journal TEXT, 
                 emotions TEXT, 
                 triggers TEXT, 
                 risk_level TEXT, 
                 recommendation TEXT,
                 created_at TIMESTAMP)''')
    conn.commit()
    conn.close()


init_db()

# --- AI ENGINE ---
# Note: In a real app, use st.secrets for the API Key
client = OpenAI(api_key="YOUR_OPENAI_API_KEY")


def analyze_student_mindset(journal_text, exam_type):
    prompt = f"""
    You are an empathetic AI Mental Wellness Coach for students preparing for competitive exams like {exam_type}.
    Analyze this journal entry: "{journal_text}"

    Provide a JSON response with:
    1. primary_emotions (List of strings)
    2. stress_trigger (Choose from: Academic Pressure, Peer Comparison, Time Management, Family Expectations, Self-Doubt, or Other)
    3. risk_level (Low, Medium, High, Critical)
    4. personalized_advice (Exam-specific, short, and actionable)
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Return only JSON."},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "primary_emotions": ["Unknown"],
            "stress_trigger": "Analysis Pending",
            "risk_level": "Low",
            "personalized_advice": "Keep going! You are doing your best."
        }


# --- UI COMPONENTS ---
def login_section():
    st.title("🧠 ExamMind AI")
    st.subheader("Your AI-Powered Mental Wellness Companion")

    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Student Name")
    with col2:
        exam = st.selectbox("Target Exam", ["JEE", "NEET", "CUET", "CAT", "GATE", "UPSC"])

    if st.button("Start My Session"):
        if username:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.exam = exam
            st.rerun()


def daily_checkin():
    st.header(f"Welcome back, {st.session_state.username}!")
    st.info(f"Focusing on: **{st.session_state.exam}**")

    with st.container():
        col1, col2 = st.columns([1, 2])
        with col1:
            mood = st.select_slider("How are you feeling today?", options=[1, 2, 3, 4, 5], value=3)
            st.caption("1: Very Low | 5: Excellent")

        with col2:
            journal = st.text_area("Write a few lines about your day (study progress, fears, thoughts)...",
                                   placeholder="e.g., I'm feeling overwhelmed by the mock test scores today.")

    if st.button("Analyze My Mindset"):
        if journal:
            with st.spinner("AI is analyzing your patterns..."):
                # AI Analysis
                analysis = analyze_student_mindset(journal, st.session_state.exam)

                # Save to DB
                conn = sqlite3.connect('exammind.db')
                c = conn.cursor()
                c.execute(
                    "INSERT INTO logs (username, mood_score, journal, emotions, triggers, risk_level, recommendation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (st.session_state.username, mood, journal,
                     ", ".join(analysis['primary_emotions']),
                     analysis['stress_trigger'],
                     analysis['risk_level'],
                     analysis['personalized_advice'],
                     datetime.now()))
                conn.commit()
                conn.close()
                st.success("Entry Saved! View your insights below.")
                st.session_state.last_analysis = analysis
        else:
            st.warning("Please write something in your journal first.")


def dashboard():
    st.divider()
    st.header("📊 Your Wellness Dashboard")

    conn = sqlite3.connect('exammind.db')
    df = pd.read_sql_query(f"SELECT * FROM logs WHERE username='{st.session_state.username}'", conn)
    conn.close()

    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])

        # Metrics
        m1, m2, m3 = st.columns(3)
        avg_mood = df['mood_score'].mean()
        m1.metric("Avg Mood Score", f"{avg_mood:.1f} / 5")
        m2.metric("Latest Risk Level", df['risk_level'].iloc[-1])
        m3.metric("Top Trigger", df['triggers'].mode()[0])

        # Charts
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Mood Trend")
            fig_mood = px.line(df, x='created_at', y='mood_score', markers=True, color_discrete_sequence=['#4A90E2'])
            st.plotly_chart(fig_mood, use_container_width=True)

        with c2:
            st.subheader("Stress Distribution")
            fig_pie = px.pie(df, names='triggers', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        # AI Recommendation Box
        st.subheader("💡 Latest AI Insight")
        latest = df.iloc[-1]
        risk_class = "low-risk" if latest['risk_level'] == "Low" else "med-risk" if latest[
                                                                                        'risk_level'] == "Medium" else "high-risk"

        st.markdown(f"""
            <div class="status-box {risk_class}">
                <strong>Detected Emotions:</strong> {latest['emotions']}<br>
                <strong>Trigger:</strong> {latest['triggers']}<br>
                <strong>Advice:</strong> {latest['recommendation']}
            </div>
            """, unsafe_allow_index=True)

        if latest['risk_level'] in ['High', 'Critical']:
            st.error("⚠️ High stress detected. Please consider talking to a mentor or taking a 24-hour break.")
    else:
        st.write("No data yet. Complete your first check-in!")


# --- MAIN APP FLOW ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        login_section()
    else:
        # Sidebar Navigation
        st.sidebar.title(f"Hi, {st.session_state.username}")
        page = st.sidebar.radio("Navigation", ["Daily Check-In", "Progress Dashboard", "Exam Motivation"])

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        if page == "Daily Check-In":
            daily_checkin()
        elif page == "Progress Dashboard":
            dashboard()
        elif page == "Exam Motivation":
            st.header("🎯 Personalized Motivation")
            st.write("Based on your goals, remember: 'Preparation is a marathon, not a sprint.'")
            st.video("https://www.youtube.com/watch?v=mZ7pUADoo58")  # Example Study Lofi


if __name__ == "__main__":
    main()