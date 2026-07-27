"""Validated answers and provider mappings."""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Deployment(StrEnum):
    PHYSICAL = "physical"
    SIMULATOR = "simulator"


class LLMProvider(StrEnum):
    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


PROVIDER_DEFAULTS: dict[LLMProvider, tuple[str, str]] = {
    LLMProvider.BEDROCK: ("gemma-4-26b-bedrock-eu-central-1", "BEDROCK_API_KEY"),
    LLMProvider.OPENAI: ("gpt-4.1", "OPENAI_API_KEY"),
    LLMProvider.ANTHROPIC: ("claude-sonnet-4-5", "ANTHROPIC_API_KEY"),
    LLMProvider.CUSTOM: ("custom-model", "CUSTOM_LLM_API_KEY"),
}


class SetupAnswers(BaseModel):
    schema_version: Literal[2] = 2
    deployment: Deployment
    robot_host: str | None = None
    robot_id: int | None = Field(default=None, ge=0, le=232)
    robot_domain_id: int = Field(default=0, ge=0, le=232)
    perception_domain_id: int = Field(default=200, ge=0, le=232)
    llm_provider: LLMProvider = LLMProvider.BEDROCK
    llm_model_id: str = "gemma-4-26b-bedrock-eu-central-1"
    llm_api_base: str | None = None
    zoom_h8_enabled: bool = True
    kinect_enabled: bool = True
    kinect_transcription_enabled: bool = False
    groot_enabled: bool = False
    viz_port: int = Field(default=5173, ge=1, le=65535)
    rosbridge_port: int = Field(default=9090, ge=1, le=65535)
    llm_port: int = Field(default=4050, ge=1, le=65535)
    gpu_available: bool = True
    ipad_enabled: bool = False
    projector_enabled: bool = False
    launch_after_setup: bool = True

    @field_validator("robot_host")
    @classmethod
    def normalize_host(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.removesuffix(".").lower()

    @model_validator(mode="after")
    def validate_deployment(self) -> "SetupAnswers":
        if self.deployment == Deployment.PHYSICAL:
            if not self.robot_host:
                raise ValueError("A physical deployment requires robot_host")
            match = re.fullmatch(r"haru-(\d+)(?:\.local)?", self.robot_host)
            if not match:
                raise ValueError("Robot hostname must match haru-N or haru-N.local")
            detected_id = int(match.group(1))
            if self.robot_id is None:
                self.robot_id = detected_id
            if self.robot_id != detected_id:
                raise ValueError("robot_id must match the selected hostname")
            self.robot_domain_id = detected_id
        ports = (
            self.viz_port,
            self.llm_port,
            self.rosbridge_port,
            self.rosbridge_port + 1,
            self.rosbridge_port + 2,
            self.rosbridge_port + 3,
        )
        if self.rosbridge_port > 65532:
            raise ValueError("ROS bridge base port must leave room for four consecutive ports")
        if len(set(ports)) != len(ports):
            raise ValueError("viz, ROS bridge, and LLM host ports must be distinct")
        return self

    @property
    def secret_name(self) -> str:
        return PROVIDER_DEFAULTS[self.llm_provider][1]


AGENT_MODEL_KEYS = (
    "HARU_AGENT_MODEL_ID",
    "HARU_JP_AGENT_MODEL_ID",
    "GOAL_AGENT_MODEL_ID",
    "GOAL_INFERENCE_AGENT_MODEL_ID",
    "GAZING_AGENT_MODEL_ID",
    "TTS_AGENT_MODEL_ID",
    "EXPRESSIVE_BEHAVIOR_AGENT_MODEL_ID",
    "SUMMARY_AGENT_MODEL_ID",
    "SYNCED_ROUTINES_AGENT_MODEL_ID",
    "MICRO_ROUTINES_AGENT_MODEL_ID",
)
