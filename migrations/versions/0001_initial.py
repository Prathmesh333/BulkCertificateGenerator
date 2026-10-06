"""Initial job and certificate tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("generation_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("course_name", sa.String(), nullable=False),
        sa.Column("issue_date", sa.String(), nullable=False),
        sa.Column("template_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("started_at", sa.String()), sa.Column("completed_at", sa.String()))
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])
    op.create_table("certificate_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("generation_jobs.id"), nullable=False),
        sa.Column("input_index", sa.Integer(), nullable=False),
        sa.Column("client_reference", sa.String()), sa.Column("recipient_name", sa.String()),
        sa.Column("email", sa.String()), sa.Column("status", sa.String(), nullable=False),
        sa.Column("certificate_id", sa.String(), unique=True), sa.Column("output_key", sa.String()),
        sa.Column("error_stage", sa.String()), sa.Column("error_code", sa.String()),
        sa.Column("error_message", sa.String()), sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String()), sa.Column("completed_at", sa.String()),
        sa.UniqueConstraint("job_id", "input_index"))
    op.create_index("ix_certificate_items_job_id", "certificate_items", ["job_id"])
    op.create_index("ix_certificate_items_status", "certificate_items", ["status"])


def downgrade():
    op.drop_table("certificate_items")
    op.drop_table("generation_jobs")
