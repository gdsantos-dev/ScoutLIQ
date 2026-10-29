"""Human review records supplement Lead; snapshots never rewrite production scores."""
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from .models import uid


class LearningGate(Base):
    __tablename__ = 'learning_gate'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class LearningCase(Base):
    __tablename__ = 'learning_cases'
    __table_args__ = (UniqueConstraint('user_id', 'source', 'external_id', name='uq_learning_source'),
                      UniqueConstraint('user_id', 'identity_key', name='uq_learning_identity'))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    lead_id: Mapped[str | None] = mapped_column(ForeignKey('leads.id', ondelete='SET NULL'), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(100))
    identity_key: Mapped[str] = mapped_column(String(64))
    dataset: Mapped[str] = mapped_column(String(80))
    split: Mapped[str] = mapped_column(String(20))
    record_json: Mapped[str] = mapped_column(Text)
    system_json: Mapped[str] = mapped_column(Text)
    record_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[int] = mapped_column(Integer)
    __mapper_args__ = {'version_id_col': version}


class LearningRevision(Base):
    __tablename__ = 'learning_revisions'
    __table_args__ = (UniqueConstraint('case_id', 'version', name='uq_learning_revision'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey('learning_cases.id', ondelete='CASCADE'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[int] = mapped_column(Integer)


class LearningImport(Base):
    __tablename__ = 'learning_imports'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_learning_import'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    input_hash: Mapped[str] = mapped_column(String(64))
    preview_json: Mapped[str] = mapped_column(Text)
    receipt_json: Mapped[str] = mapped_column(Text, default='{}')
    expires_at: Mapped[int] = mapped_column(Integer)
    committed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class LearningEvaluation(Base):
    __tablename__ = 'learning_evaluations'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_learning_evaluation'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    input_hash: Mapped[str] = mapped_column(String(64))
    dataset: Mapped[str] = mapped_column(String(80))
    snapshot_json: Mapped[str] = mapped_column(Text)
    report_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer)


class ScoreConfiguration(Base):
    __tablename__ = 'score_configurations'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, default='{}')
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {'version_id_col': version}


class CalibrationProposal(Base):
    __tablename__ = 'calibration_proposals'
    __table_args__ = (UniqueConstraint('user_id', 'request_key', name='uq_calibration_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    input_hash: Mapped[str] = mapped_column(String(64))
    report_json: Mapped[str] = mapped_column(Text)
    base_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer)


class CalibrationChange(Base):
    __tablename__ = 'calibration_changes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey('calibration_proposals.id', ondelete='SET NULL'), nullable=True)
    reverted_change_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    previous_json: Mapped[str] = mapped_column(Text)
    applied_json: Mapped[str] = mapped_column(Text)
    config_version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[int] = mapped_column(Integer)


# New leads inherit only a configuration already explicitly approved by this user.
# The scorer stays pure and detached worker snapshots carry the same configuration.
from sqlalchemy import event, select
from .models import Lead


@event.listens_for(Lead, 'before_insert')
def inherit_approved_criteria(mapper, connection, target):
    cfg = connection.execute(select(ScoreConfiguration.config_json).where(ScoreConfiguration.user_id == target.user_id)).scalar()
    target.score_criteria_json = cfg or '{}'
