"""
Streamlit Web Dashboard for Robot Control and Monitoring
"""

import streamlit as st
import requests
import json
import plotly.graph_objects as go
from datetime import datetime
import time

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="VLA Robot Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .status-box {
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<p class="main-header">🤖 Vision-Language Robotic Assistant</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Control Panel")

    # Robot connection status
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ Robot Connected")
        else:
            st.error("❌ Robot Disconnected")
    except:
        st.error("❌ Cannot reach robot")

    st.divider()

    # Quick actions
    st.subheader("Quick Actions")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

    if st.button("🛑 Emergency Stop", use_container_width=True):
        try:
            requests.post(f"{API_URL}/api/v1/state/emergency_stop")
            st.warning("Emergency stop activated!")
        except:
            st.error("Failed to send emergency stop")

    st.divider()

    # Settings
    st.subheader("Settings")
    auto_refresh = st.checkbox("Auto-refresh (5s)", value=False)

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs(["🎮 Control", "📊 Status", "👁️ Perception", "📈 Metrics"])

# Tab 1: Control
with tab1:
    st.header("Robot Command Interface")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Natural Language Commands")

        command = st.text_input(
            "Enter command:",
            placeholder="e.g., Pick up the red bottle from the left table",
            key="command_input"
        )

        if st.button("🚀 Execute Command", type="primary", use_container_width=True):
            if command:
                with st.spinner("Executing command..."):
                    try:
                        response = requests.post(
                            f"{API_URL}/api/v1/command",
                            json={"query": command}
                        )

                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ {result['message']}")
                            st.info(f"Task ID: {result['task_id']}")
                        else:
                            st.error(f"❌ Error: {response.text}")
                    except Exception as e:
                        st.error(f"❌ Failed to execute: {str(e)}")
            else:
                st.warning("Please enter a command")

        st.divider()

        # Recent tasks
        st.subheader("Recent Tasks")
        try:
            response = requests.get(f"{API_URL}/api/v1/commands?limit=5")
            if response.status_code == 200:
                tasks = response.json()
                for task in tasks:
                    status_color = {
                        "completed": "🟢",
                        "in_progress": "🟡",
                        "failed": "🔴",
                        "pending": "⚪"
                    }.get(task["status"], "⚪")

                    st.text(f"{status_color} {task['task_id'][:8]}... - {task['current_step'] or 'Waiting'}")
        except:
            st.warning("Could not load tasks")

    with col2:
        st.subheader("Example Commands")
        examples = [
            "Navigate to the kitchen",
            "Pick up the red bottle",
            "What objects do you see?",
            "Where did I leave my keys?",
            "Scan the environment",
            "Check battery level"
        ]

        for ex in examples:
            if st.button(ex, use_container_width=True):
                st.session_state.command_input = ex
                st.rerun()

# Tab 2: Status
with tab2:
    st.header("Robot Status")

    try:
        response = requests.get(f"{API_URL}/api/v1/state")
        if response.status_code == 200:
            state = response.json()

            # Status cards
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Battery", f"{state['battery_level']:.1f}%")

            with col2:
                st.metric("Gripper", state['gripper_state'].title())

            with col3:
                st.metric("Moving", "Yes" if state['is_moving'] else "No")

            with col4:
                st.metric("Current Task", state['current_task'] or "None")

            st.divider()

            # Position visualization
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Position")
                pos = state['position']
                st.json({
                    "X": f"{pos['x']:.2f} m",
                    "Y": f"{pos['y']:.2f} m",
                    "Z": f"{pos['z']:.2f} m"
                })

            with col2:
                st.subheader("Orientation")
                orient = state['orientation']
                st.json({
                    "Roll": f"{orient['roll']:.2f}°",
                    "Pitch": f"{orient['pitch']:.2f}°",
                    "Yaw": f"{orient['yaw']:.2f}°"
                })

    except Exception as e:
        st.error(f"Failed to load robot state: {str(e)}")

# Tab 3: Perception
with tab3:
    st.header("Visual Perception")

    try:
        response = requests.get(f"{API_URL}/api/v1/state/perception")
        if response.status_code == 200:
            perception = response.json()

            st.subheader(f"🔍 Detected Objects ({len(perception.get('objects_detected', []))})")

            objects = perception.get('objects_detected', [])
            if objects:
                for obj in objects:
                    with st.expander(f"{obj['class_name']} (ID: {obj['object_id']})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Confidence:** {obj['confidence']:.2%}")
                        with col2:
                            pos = obj['position']
                            st.write(f"**Position:** ({pos['x']:.2f}, {pos['y']:.2f}, {pos['z']:.2f})")
            else:
                st.info("No objects currently detected")

    except Exception as e:
        st.error(f"Failed to load perception data: {str(e)}")

# Tab 4: Metrics
with tab4:
    st.header("System Metrics")

    # Placeholder metrics
    col1, col2 = st.columns(2)

    with col1:
        # Battery history chart
        st.subheader("Battery History")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=list(range(10)),
            y=[90, 88, 86, 85, 83, 82, 81, 80, 79, 78],
            mode='lines+markers',
            name='Battery %',
            line=dict(color='green', width=3)
        ))

        fig.update_layout(
            xaxis_title="Time (minutes ago)",
            yaxis_title="Battery %",
            height=300
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Tasks completed
        st.subheader("Tasks Completed")

        fig = go.Figure(data=[go.Pie(
            labels=['Completed', 'Failed', 'In Progress'],
            values=[15, 2, 1],
            hole=.3
        )])

        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

# Auto-refresh
if auto_refresh:
    time.sleep(5)
    st.rerun()
