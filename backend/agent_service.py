"""
react_agent.py — LlamaIndex React Agent implementation.

This module implements a React (Reasoning and Acting) agent using LlamaIndex
that can analyze data and provide structured responses.
"""

import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.anthropic import Anthropic
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import yfinance as yf
from io import StringIO
import base64
import traceback
import sys
from contextlib import redirect_stdout, redirect_stderr

from models import AnalyzeRequest, AnalyzeResponse



class ReactDataAgent:
    """React Agent for data analysis using LlamaIndex with OpenAI client for Anthropic."""
    
    def __init__(self):
        """Initialize the React agent with LlamaIndex."""
        # Initialize OpenAI client configured for Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        
        # Use Anthropic client
        self.llm = Anthropic(
            api_key=api_key,
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=2048,
            temperature=0.1
        )
        
        # # Create tools
        # self.tools = [
        #     FunctionTool.from_defaults(
        #         fn=python_code_executor,
        #         name="execute_python",
        #         description="Execute Python code for data analysis. Use this to run pandas, numpy, matplotlib, seaborn, or yfinance code."
        #     ),
        #     FunctionTool.from_defaults(
        #         fn=data_analysis_tool,
        #         name="analyze_data",
        #         description="Get suggestions for data analysis approaches based on natural language queries."
        #     )
        # ]
        
        # Create the React agent (using new workflow-based constructor)
        system_prompt = """You are an AI Data Analyst with React (Reasoning and Acting) capabilities.

Your role is to help users with data analysis tasks using a structured approach:

1. THINK: Reason about what analysis is needed based on the user's request
2. ACT: Use available tools when needed to execute analysis or get suggestions
3. OBSERVE: Interpret any results from tool usage
4. RESPOND: Provide clear, actionable insights and explanations

You should:
- Ask clarifying questions when the request is unclear
- Suggest appropriate analysis methods for different types of data
- Explain your reasoning process clearly
- Provide practical, actionable insights
- Be conversational and helpful

Focus on being a knowledgeable data analysis assistant that can guide users through their analytical needs."""

        self.agent = ReActAgent(
            name="Data Analysis Agent",
            description="An AI agent specialized in data analysis using React approach",
            system_prompt=system_prompt,
            tools=[],
            llm=self.llm,
            verbose=True
        )
    
    def analyze(self, request: AnalyzeRequest) -> AnalyzeResponse:
        """
        Analyze data using the React agent in chat-based format.
        
        Args:
            request: Analysis request containing prompt and history
            
        Returns:
            Structured analysis response
        """
        try:
            # Convert history to LlamaIndex ChatMessage format
            from llama_index.core.base.llms.types import ChatMessage, MessageRole
            
            chat_history = []
            for msg in request.history:
                role = MessageRole.USER if msg.role.lower() == "user" else MessageRole.ASSISTANT
                chat_history.append(ChatMessage(role=role, content=msg.content))
            
            # Get response from agent using chat-based format
            import asyncio
            
            async def run_agent():
                if chat_history:
                    # Use chat_history if we have previous conversation
                    result = await self.agent.run(
                        user_msg=request.prompt,
                        chat_history=chat_history
                    )
                else:
                    # For first message, just use user_msg
                    result = await self.agent.run(user_msg=request.prompt)
                return result
            
            # Run the async agent
            response = asyncio.run(run_agent())
            
            return AnalyzeResponse(
                summary=str(response),
                raw_llm_response=str(response)
            )
            
        except Exception as e:
            error_msg = f"React agent error: {str(e)}\n{traceback.format_exc()}"
            return AnalyzeResponse(
                summary=f"I encountered an error while processing your request: {str(e)}",
                error=error_msg,
                raw_llm_response=error_msg
            )
    
    def reset_memory(self):
        """Reset the agent's conversation memory."""
        self.memory.reset()


# Global agent instance
_agent_instance = None


def get_react_agent() -> ReactDataAgent:
    """Get or create the global React agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReactDataAgent()
    return _agent_instance


def run_react_agent(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run analysis using the React agent.
    
    Args:
        request: Analysis request
        
    Returns:
        Analysis response
    """
    agent = get_react_agent()
    return agent.analyze(request)