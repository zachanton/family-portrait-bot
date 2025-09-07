# aiogram_bot_template/db/repo/analytics.py
from dataclasses import dataclass, field
from aiogram_bot_template.db.db_api.storages import PostgresConnection


@dataclass
class FunnelStats:
    photos_collected: int = 0
    quality_selected: int = 0
    awaiting_payment: int = 0
    paid: int = 0
    completed: int = 0


@dataclass
class RevenueStats:
    total_stars: int = 0


# --- ИЗМЕНЕНИЕ: Упрощенный датакласс ---
@dataclass
class FeatureUsageStats:
    group_photo: int = 0


@dataclass
class PaidTierUsageStats:
    quality_1: int = 0
    quality_2: int = 0
    quality_3: int = 0


@dataclass
class AnalyticsData:
    new_users: int = 0
    funnel: FunnelStats = field(default_factory=FunnelStats)
    revenue: RevenueStats = field(default_factory=RevenueStats)
    feature_usage: FeatureUsageStats = field(default_factory=FeatureUsageStats)
    paid_tier_usage: PaidTierUsageStats = field(default_factory=PaidTierUsageStats)


async def get_summary_statistics(db: PostgresConnection, interval_days: int) -> AnalyticsData:
    """Fetches key business metrics for a given period."""
    interval_str = f"'{interval_days} days'"

    sql_users = "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL " + interval_str
    new_users_res = await db.fetchrow(sql_users)

    # --- ИЗМЕНЕНИЕ: Упрощенный запрос для воронки ---
    sql_funnel = f"""
        SELECT
            COUNT(id) AS photos_collected,
            COUNT(id) FILTER (WHERE status IN ('quality_selected', 'awaiting_payment', 'paid', 'processing', 'completed')) AS quality_selected,
            COUNT(id) FILTER (WHERE status IN ('awaiting_payment', 'paid', 'processing', 'completed')) AS awaiting_payment,
            COUNT(id) FILTER (WHERE status IN ('paid', 'processing', 'completed')) AS paid,
            COUNT(id) FILTER (WHERE status = 'completed') AS completed
        FROM generation_requests
        WHERE created_at >= NOW() - INTERVAL {interval_str};
    """
    funnel_res = await db.fetchrow(sql_funnel)

    sql_revenue = f"""
        SELECT COALESCE(SUM(p.amount), 0) as total
        FROM payments p
        JOIN generation_requests gr ON p.request_id = gr.id
        WHERE gr.created_at >= NOW() - INTERVAL {interval_str};
    """
    revenue_res = await db.fetchrow(sql_revenue)

    # --- ИЗМЕНЕНИЕ: Запрос теперь группирует только по одному типу ---
    sql_feature_usage = f"""
        SELECT
            type,
            COUNT(*) AS count
        FROM generations
        WHERE created_at >= NOW() - INTERVAL {interval_str} AND status = 'completed'
        GROUP BY type;
    """
    feature_usage_res = await db.fetch(sql_feature_usage)

    sql_paid_tier_usage = f"""
        SELECT
            quality_level,
            COUNT(*) AS count
        FROM generations
        WHERE created_at >= NOW() - INTERVAL {interval_str}
          AND quality_level > 0 AND status = 'completed'
        GROUP BY quality_level;
    """
    paid_tier_usage_res = await db.fetch(sql_paid_tier_usage)

    feature_usage_data = {row['type']: row['count'] for row in feature_usage_res.data}
    paid_tier_data = {f"quality_{row['quality_level']}": row['count'] for row in paid_tier_usage_res.data}

    return AnalyticsData(
        new_users=new_users_res.data["count"] if new_users_res.data else 0,
        funnel=FunnelStats(**funnel_res.data) if funnel_res.data else FunnelStats(),
        revenue=RevenueStats(total_stars=revenue_res.data["total"]) if revenue_res.data else RevenueStats(),
        feature_usage=FeatureUsageStats(**feature_usage_data),
        paid_tier_usage=PaidTierUsageStats(**paid_tier_data),
    )