"""
LangChain Agent for Robot Control
Implements ReAct-style agent with tool use for embodied AI
"""

from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from typing import List, Dict, Any
import logging
import os
import httpx
import json

logger = logging.getLogger(__name__)


class RobotAgent:
    """
    LangChain-based agent for robotic control
    Uses ReAct prompting with tools for perception, navigation, and manipulation
    """

    def __init__(self, mcp_server_url: str = "http://api:8000/mcp"):
        """
        Initialize robot agent

        Args:
            mcp_server_url: URL of MCP server for robot control
        """
        self.mcp_url = mcp_server_url

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4-turbo-preview"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Initialize tools
        self.tools = self._create_tools()

        # Create prompt
        self.prompt = self._create_prompt()

        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Create agent
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # Create executor
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )

        logger.info("Robot Agent initialized successfully")

    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent"""

        tools = [
            Tool(
                name="Navigate",
                func=self._navigate_tool,
                description="""
                Navigate the robot to a specified location.
                Input: location name (e.g., 'kitchen', 'left_table', 'living_room')
                Returns: Navigation status
                """
            ),
            Tool(
                name="GetPerception",
                func=self._get_perception_tool,
                description="""
                Get current visual perception data from robot's camera.
                Input: None (leave blank)
                Returns: List of detected objects with positions
                """
            ),
            Tool(
                name="PickObject",
                func=self._pick_object_tool,
                description="""
                Pick up an object using the robot's gripper.
                Input: object_id (e.g., 'obj_001')
                Returns: Success/failure status
                """
            ),
            Tool(
                name="PlaceObject",
                func=self._place_object_tool,
                description="""
                Place the currently held object at a location.
                Input: target location name
                Returns: Success/failure status
                """
            ),
            Tool(
                name="QueryMemory",
                func=self._query_memory_tool,
                description="""
                Query the robot's long-term memory (GraphRAG knowledge graph).
                Input: natural language query (e.g., 'Where did I last see the red bottle?')
                Returns: Retrieved facts and knowledge
                """
            ),
            Tool(
                name="GetMap",
                func=self._get_map_tool,
                description="""
                Get the current SLAM map and known locations.
                Input: None
                Returns: Map data with known locations
                """
            ),
            Tool(
                name="CheckBattery",
                func=self._check_battery_tool,
                description="""
                Check robot's battery level.
                Input: None
                Returns: Battery percentage
                """
            ),
            Tool(
                name="ScanEnvironment",
                func=self._scan_environment_tool,
                description="""
                Perform a 360-degree environment scan.
                Input: None
                Returns: Scan results with newly detected objects
                """
            )
        ]

        return tools

    def _call_mcp(self, action: str, parameters: dict = None) -> Dict[str, Any]:
        """
        Call MCP server to execute action

        Args:
            action: MCP action name
            parameters: Action parameters

        Returns:
            MCP response
        """
        try:
            response = httpx.post(
                f"{self.mcp_url}/execute",
                json={
                    "action": action,
                    "parameters": parameters or {},
                    "context": {}
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            return {"status": "failure", "error": str(e)}

    # Tool implementations
    def _navigate_tool(self, location: str) -> str:
        """Navigate to location"""
        result = self._call_mcp("NAVIGATE", {"location": location})
        if result.get("status") == "success":
            return f"Successfully started navigation to {location}"
        return f"Navigation failed: {result.get('error', 'Unknown error')}"

    def _get_perception_tool(self, _: str = "") -> str:
        """Get perception data"""
        result = self._call_mcp("GET_PERCEPTION")
        if result.get("status") == "success":
            data = result.get("result", {})
            objects = data.get("objects", [])
            return f"Detected {len(objects)} objects: {json.dumps(objects)}"
        return "Failed to get perception data"

    def _pick_object_tool(self, object_id: str) -> str:
        """Pick object"""
        result = self._call_mcp("PICK_OBJECT", {"object_id": object_id})
        if result.get("status") == "success":
            return f"Successfully picked up object {object_id}"
        return f"Failed to pick object: {result.get('error')}"

    def _place_object_tool(self, location: str) -> str:
        """Place object"""
        result = self._call_mcp("PLACE_OBJECT", {"target_location": location})
        if result.get("status") == "success":
            return f"Successfully placed object at {location}"
        return f"Failed to place object: {result.get('error')}"

    def _query_memory_tool(self, query: str) -> str:
        """Query memory"""
        result = self._call_mcp("GET_MEMORY", {"query": query})
        if result.get("status") == "success":
            data = result.get("result", {})
            facts = data.get("facts", [])
            return f"Memory results: {json.dumps(facts)}"
        return "No memory results found"

    def _get_map_tool(self, _: str = "") -> str:
        """Get map"""
        result = self._call_mcp("GET_MAP")
        if result.get("status") == "success":
            return f"Map data: {json.dumps(result.get('result'))}"
        return "Failed to get map"

    def _check_battery_tool(self, _: str = "") -> str:
        """Check battery"""
        result = self._call_mcp("GET_BATTERY")
        if result.get("status") == "success":
            level = result.get("result", {}).get("battery_level", 0)
            return f"Battery level: {level}%"
        return "Failed to check battery"

    def _scan_environment_tool(self, _: str = "") -> str:
        """Scan environment"""
        result = self._call_mcp("SCAN_ENVIRONMENT")
        if result.get("status") == "success":
            return f"Scan complete: {json.dumps(result.get('result'))}"
        return "Scan failed"

    def _create_prompt(self) -> PromptTemplate:
        """Create ReAct prompt template"""

        template = """You are an intelligent robotic assistant that can see, understand, and interact with the physical world.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question/command you must respond to
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question/command

Important guidelines:
1. Break down complex commands into simple steps
2. Use perception before navigation or manipulation
3. Check memory for known locations before asking user
4. Be safe - verify actions won't harm anyone or break anything
5. Provide clear, concise responses to the user

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

        return PromptTemplate(
            template=template,
            input_variables=["input", "agent_scratchpad"],
            partial_variables={
                "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools]),
                "tool_names": ", ".join([tool.name for tool in self.tools])
            }
        )

    def execute_command(self, command: str) -> str:
        """
        Execute a natural language command

        Args:
            command: Natural language instruction

        Returns:
            Agent's response
        """
        logger.info(f"Executing command: {command}")

        try:
            result = self.executor.invoke({"input": command})
            response = result.get("output", "Command completed")
            logger.info(f"Command result: {response}")
            return response

        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"


# Example usage
if __name__ == "__main__":
    agent = RobotAgent()
    response = agent.execute_command("Pick up the red bottle from the left table")
    print(response)
