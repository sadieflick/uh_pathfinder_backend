"""Association tables for many-to-many relationships."""

from datetime import datetime
from sqlalchemy import Table, Column, String, Float, DateTime, ForeignKey

from ..base import Base

# NOTE: The O*NET 'skills' table in the Skill model already serves as the 
# occupation-skill association table (composite PK of onetsoc_code, element_id, scale_id).
# No separate association table needed for occupation_skill relationship.

# NOTE: The O*NET 'interests' table in the Interest model already serves as the
# occupation-interest association table (composite PK of onetsoc_code, element_id, scale_id).
# No separate association table needed for occupation_interest relationship.

# Program <-> (Pathfinder) Occupation relationship
# Note: 'public' schema (not an O*NET table, occupation maps one-to-one with onet.occupation_data)
program_occupation_association = Table(
    "program_occupation_association",
    Base.metadata,
    Column(
        "program_id",
        String(100),  # Increased from 50 to 100 to handle longer program IDs
        ForeignKey("programs.id", ondelete="CASCADE"), # Stays in public
        primary_key=True
    ),
    Column(
        "occupation_onet_code",
        String(10),
        # IMPORTANT: Reference the public.occupation table, not directly the O*NET table,
        # so SQLAlchemy can automatically determine join conditions for Program.occupations.
        # Occupation.onet_code itself is a FK to onet.occupation_data.onetsoc_code.
        ForeignKey("occupation.onet_code", ondelete="CASCADE"),
        primary_key=True
    ),
    Column(
        "added_at",
        DateTime,
        default=datetime.now(),
        nullable=False
    )
    ,
    Column(
        "confidence",
        Float,
        nullable=True,
        doc="LLM or embedding-derived confidence score for this occupation-program linkage (0-1)."
    )
)