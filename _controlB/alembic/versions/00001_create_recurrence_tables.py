"""
Alembic Migration: Create Recurrence Tables

Criar tabelas para o sistema de recorrência de compras:
- customer_purchase_history
- customer_product_recurrence
- recurrence_alert
- product_demand_forecast
- product_demand_detail
- intelligent_replenishment_suggestion
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "00001_create_recurrence_tables"
down_revision = "f8g9h0i1j2k3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Criar tabelas de recorrência."""
    
    # customer_purchase_history
    op.create_table(
        "customer_purchase_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sales_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("sales_channel", sa.String(length=50), nullable=False, server_default="SALES"),
        sa.Column("salesman_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_order.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["salesman_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_history_customer_product_date",
        "customer_purchase_history",
        ["organization_id", "customer_id", "product_id", "purchase_date"],
    )
    op.create_index(
        "ix_purchase_history_date_range",
        "customer_purchase_history",
        ["organization_id", "purchase_date"],
    )
    op.create_index(
        "ix_purchase_history_customer_date",
        "customer_purchase_history",
        ["customer_id", "purchase_date"],
    )
    
    # customer_product_recurrence
    op.create_table(
        "customer_product_recurrence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_purchases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_purchase_date", sa.Date(), nullable=True),
        sa.Column("first_purchase_date", sa.Date(), nullable=True),
        sa.Column("average_days_between_purchases", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("last_interval_days", sa.Integer(), nullable=True),
        sa.Column("purchase_frequency_type", sa.String(length=50), nullable=False, server_default="IRREGULAR"),
        sa.Column("predicted_next_purchase_date", sa.Date(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0.00"),
        sa.Column("average_quantity_per_purchase", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("last_purchase_quantity", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("recurrence_status", sa.String(length=50), nullable=False, server_default="INACTIVE"),
        sa.Column("is_critical_for_retention", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("relevance_score", sa.Numeric(precision=5, scale=2), nullable=False, server_default="50.00"),
        sa.Column("custom_recurrence_interval_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "customer_id", "product_id",
            name="uq_recurrence_org_customer_product",
        ),
    )
    op.create_index(
        "ix_recurrence_predicted_date",
        "customer_product_recurrence",
        ["organization_id", "predicted_next_purchase_date"],
    )
    op.create_index(
        "ix_recurrence_status_date",
        "customer_product_recurrence",
        ["organization_id", "recurrence_status", "predicted_next_purchase_date"],
    )
    
    # recurrence_alert
    op.create_table(
        "recurrence_alert",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recurrence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(length=50), nullable=False, server_default="REPURCHASE_DUE"),
        sa.Column("expected_purchase_date", sa.Date(), nullable=False),
        sa.Column("days_until_purchase", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="OPEN"),
        sa.Column("contact_result", sa.String(length=50), nullable=True),
        sa.Column("contact_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contacted_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contacted_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunity.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recurrence_id"], ["customer_product_recurrence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_status_date",
        "recurrence_alert",
        ["organization_id", "status", "expected_purchase_date"],
    )
    op.create_index(
        "ix_alert_customer_status",
        "recurrence_alert",
        ["customer_id", "status"],
    )
    op.create_index(
        "ix_alert_opportunity",
        "recurrence_alert",
        ["opportunity_id"],
    )
    
    # product_demand_forecast
    op.create_table(
        "product_demand_forecast",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("forecast_start_date", sa.Date(), nullable=False),
        sa.Column("forecast_end_date", sa.Date(), nullable=False),
        sa.Column("total_customers_with_recurrence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("predicted_total_quantity", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("predicted_total_revenue", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0.00"),
        sa.Column("number_of_critical_customers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0.00"),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "product_id", "forecast_start_date", "forecast_end_date",
            name="uq_demand_forecast_org_product_window",
        ),
    )
    op.create_index(
        "ix_demand_forecast_risk",
        "product_demand_forecast",
        ["organization_id", "risk_score"],
    )
    op.create_index(
        "ix_demand_forecast_valid",
        "product_demand_forecast",
        ["organization_id", "valid_until"],
    )
    
    # product_demand_detail
    op.create_table(
        "product_demand_detail",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("demand_forecast_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("predicted_quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("predicted_purchase_date", sa.Date(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["demand_forecast_id"], ["product_demand_forecast.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_demand_detail_forecast_customer",
        "product_demand_detail",
        ["demand_forecast_id", "customer_id"],
    )
    
    # intelligent_replenishment_suggestion
    op.create_table(
        "intelligent_replenishment_suggestion",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("demand_forecast_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_stock_quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("minimum_stock_level", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("safety_stock_level", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("predicted_demand_quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("demand_forecast_window_days", sa.Integer(), nullable=False),
        sa.Column("pending_purchase_orders_quantity", sa.Numeric(precision=12, scale=4), nullable=False, server_default="0.0000"),
        sa.Column("suggested_order_quantity", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("suggested_reorder_point", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("justification", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("urgency_level", sa.String(length=50), nullable=False, server_default="MEDIUM"),
        sa.Column("stock_out_risk_days", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="OPEN"),
        sa.Column("purchase_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["demand_forecast_id"], ["product_demand_forecast.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_request_id"], ["purchase_request.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replenishment_urgency_status",
        "intelligent_replenishment_suggestion",
        ["organization_id", "urgency_level", "status"],
    )
    op.create_index(
        "ix_replenishment_risk_days",
        "intelligent_replenishment_suggestion",
        ["stock_out_risk_days"],
    )
    op.create_index(
        "ix_replenishment_product",
        "intelligent_replenishment_suggestion",
        ["product_id", "status"],
    )


def downgrade() -> None:
    """Remover tabelas de recorrência."""
    op.drop_index("ix_replenishment_product", table_name="intelligent_replenishment_suggestion")
    op.drop_index("ix_replenishment_risk_days", table_name="intelligent_replenishment_suggestion")
    op.drop_index("ix_replenishment_urgency_status", table_name="intelligent_replenishment_suggestion")
    op.drop_table("intelligent_replenishment_suggestion")
    
    op.drop_index("ix_demand_detail_forecast_customer", table_name="product_demand_detail")
    op.drop_table("product_demand_detail")
    
    op.drop_index("ix_demand_forecast_valid", table_name="product_demand_forecast")
    op.drop_index("ix_demand_forecast_risk", table_name="product_demand_forecast")
    op.drop_table("product_demand_forecast")
    
    op.drop_index("ix_alert_opportunity", table_name="recurrence_alert")
    op.drop_index("ix_alert_customer_status", table_name="recurrence_alert")
    op.drop_index("ix_alert_status_date", table_name="recurrence_alert")
    op.drop_table("recurrence_alert")
    
    op.drop_index("ix_recurrence_status_date", table_name="customer_product_recurrence")
    op.drop_index("ix_recurrence_predicted_date", table_name="customer_product_recurrence")
    op.drop_table("customer_product_recurrence")
    
    op.drop_index("ix_purchase_history_customer_date", table_name="customer_purchase_history")
    op.drop_index("ix_purchase_history_date_range", table_name="customer_purchase_history")
    op.drop_index("ix_purchase_history_customer_product_date", table_name="customer_purchase_history")
    op.drop_table("customer_purchase_history")
