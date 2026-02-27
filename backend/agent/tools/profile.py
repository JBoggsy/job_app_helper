"""User profile tools — read_user_profile and update_user_profile."""

from typing import Optional

from pydantic import BaseModel, Field

from ._registry import agent_tool


class UpdateUserProfileInput(BaseModel):
    content: str = Field(
        description="New markdown content for the section (or full profile if section is omitted)"
    )
    section: Optional[str] = Field(
        default=None,
        description=(
            "Profile section to update. One of: Summary, Education, Work Experience, "
            "Skills & Expertise, Fields of Interest, Salary Preferences, Location Preferences, "
            "Remote Work Preferences, Job Search Goals, Other Notes. "
            "Omit to replace the entire profile."
        ),
    )


class ProfileMixin:
    @agent_tool(
        description=(
            "Read the user's job search profile. Returns the full markdown content with sections: "
            "Summary, Education, Work Experience, Skills & Expertise, Fields of Interest, "
            "Salary Preferences, Location Preferences, Remote Work Preferences, "
            "Job Search Goals, Other Notes."
        ),
    )
    def read_user_profile(self):
        from backend.agent.user_profile import read_profile

        return {"content": read_profile()}

    @agent_tool(
        description=(
            "Update the user's job search profile. Provide 'section' to update only that section "
            "without overwriting the rest. Omit 'section' to replace the entire profile."
        ),
        args_schema=UpdateUserProfileInput,
    )
    def update_user_profile(self, content: str, section: Optional[str] = None):
        from backend.agent.user_profile import write_profile, write_profile_section, read_profile

        if section:
            write_profile_section(section, content)
        else:
            write_profile(content)
        return {"content": read_profile()}
