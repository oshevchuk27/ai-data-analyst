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
from llama_index.llms.anthropic import Anthropic
from llama_index.tools.code_interpreter import CodeInterpreterToolSpec
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
        
        # Create code interpreter tool from LlamaIndex tool spec
        code_interpreter_tools = CodeInterpreterToolSpec().to_tool_list()

        # Create the React agent (using new workflow-based constructor)
        system_prompt = """You are an AI Data Analyst. You have access to a code_interpreter tool that executes Python code.

IMPORTANT RULES:
- You MUST use the code_interpreter tool to perform ANY computation, data analysis, or data fetching — never write code in your final answer without executing it first.
- When asked to fetch stock data, run statistics, plot charts, or do any calculation, write the Python code and call code_interpreter to run it.
- Available libraries inside code_interpreter: pandas, numpy, matplotlib, seaborn, yfinance, scipy, requests.
- After observing the tool output, summarise the findings clearly for the user.
"""

        self.agent = ReActAgent(
            name="Data Analysis Agent",
            description="An AI agent specialized in data analysis using React approach",
            system_prompt=system_prompt,
            tools=code_interpreter_tools,
            llm=self.llm,
            streaming=False,
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