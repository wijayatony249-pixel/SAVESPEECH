"""Initial database schema for SAVESPEECH

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tabel users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nama', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='user', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name='chk_users_role'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Tabel analysis_results
    op.create_table(
        'analysis_results',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('label', sa.String(length=20), nullable=False),
        sa.Column('scam_category', sa.String(length=50), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("label IN ('NORMAL', 'SUSPICIOUS', 'SCAM')", name='chk_analysis_results_label'),
        sa.CheckConstraint("risk_level IN ('Low', 'Medium', 'High', 'Critical')", name='chk_analysis_results_risk_level'),
        sa.CheckConstraint("risk_score >= 0 AND risk_score <= 100", name='chk_analysis_results_risk_score'),
        sa.CheckConstraint("scam_category IS NULL OR scam_category IN ('BANK_IMPERSONATION', 'E_WALLET_IMPERSONATION', 'OTP_SCAM', 'TRANSFER_SCAM', 'ACCOUNT_BLOCKING_SCAM')", name='chk_analysis_results_scam_category'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analysis_results_job_id'), 'analysis_results', ['job_id'], unique=False)
    op.create_index(op.f('ix_analysis_results_user_id'), 'analysis_results', ['user_id'], unique=False)

    # 3. Tabel analysis_indicators (TANPA kolom transkrip/kutipan)
    op.create_table(
        'analysis_indicators',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('result_id', sa.Uuid(), nullable=False),
        sa.Column('indicator_code', sa.String(length=50), nullable=False),
        sa.Column('weight', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['result_id'], ['analysis_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_analysis_indicators_result_id'), 'analysis_indicators', ['result_id'], unique=False)

    # 4. Tabel audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'], unique=False)

    # 5. Tabel model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('metrics_json', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=False),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('model_versions')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_analysis_indicators_result_id'), table_name='analysis_indicators')
    op.drop_table('analysis_indicators')
    op.drop_index(op.f('ix_analysis_results_user_id'), table_name='analysis_results')
    op.drop_index(op.f('ix_analysis_results_job_id'), table_name='analysis_results')
    op.drop_table('analysis_results')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
