# aiogram_bot_template/db/repo/analytics.py
from dataclasses import dataclass, field
from aiogram_bot_template.db.db_api.storages import PostgresConnection


@dataclass
class FunnelStats:
    photos_collected: int = 0
    options_selected: int = 0
    quality_selected: int = 0
    awaiting_payment: int = 0
    paid: int = 0
    completed: int = 0


@dataclass
class RevenueStats:
    total_stars: int = 0


@dataclass
class FreeUsageStats:
    free_trials_used: int = 0
    whitelist_uses: int = 0


@dataclass
class ReferralStats:
    source: str
    count: int


@dataclass
class FeatureUsageStats:
    child_generation: int = 0
    image_edit: int = 0
    upscale: int = 0

@dataclass
class PaidTierUsageStats:
    quality_1: int = 0  # Good
    quality_2: int = 0  # Excellent
    quality_3: int = 0  # Premium


@dataclass
class AnalyticsData:
    new_users: int = 0
    funnel: FunnelStats = field(default_factory=FunnelStats)
    revenue: RevenueStats = field(default_factory=RevenueStats)
    free_usage: FreeUsageStats = field(default_factory=FreeUsageStats)
    feature_usage: FeatureUsageStats = field(default_factory=FeatureUsageStats)
    paid_tier_usage: PaidTierUsageStats = field(default_factory=PaidTierUsageStats)
    top_referrals: list[ReferralStats] = field(default_factory=list)

async def get_summary_statistics(db: PostgresConnection, interval_days: int) -> AnalyticsData:
    """Fetches key business metrics for a given period."""

    interval_str = f"'{interval_days} days'"

    # 1. New Users
    sql_users = "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL " + interval_str
    new_users_res = await db.fetchrow(sql_users)

    # 2. Funnel Stats (The new powerful query)
    sql_funnel = f"""
        SELECT
            COUNT(id) AS photos_collected,
            COUNT(id) FILTER (WHERE status IN ('options_selected', 'quality_selected', 'awaiting_payment', 'paid', 'processing', 'completed')) AS options_selected,
            COUNT(id) FILTER (WHERE status IN ('quality_selected', 'awaiting_payment', 'paid', 'processing', 'completed')) AS quality_selected,
            COUNT(id) FILTER (WHERE status IN ('awaiting_payment', 'paid', 'processing', 'completed')) AS awaiting_payment,
            COUNT(id) FILTER (WHERE status IN ('paid', 'processing', 'completed')) AS paid,
            COUNT(id) FILTER (WHERE status = 'completed') AS completed
        FROM generation_requests
        WHERE created_at >= NOW() - INTERVAL {interval_str};
    """
    funnel_res = await db.fetchrow(sql_funnel)

    # 3. Revenue Stats (from payments table, which is more accurate)
    sql_revenue = f"""
        SELECT COALESCE(SUM(p.amount), 0) as total
        FROM payments p
        JOIN generation_requests gr ON p.request_id = gr.id
        WHERE gr.created_at >= NOW() - INTERVAL {interval_str};
    """
    revenue_res = await db.fetchrow(sql_revenue)

    # 4. Top 5 Referral Sources (counting only users who paid)
    sql_referrals = f"""
        SELECT 
            gr.referral_source_at_creation as source, 
            COUNT(DISTINCT gr.user_id) as count
        FROM generation_requests gr
        INNER JOIN payments p ON gr.id = p.request_id
        WHERE gr.referral_source_at_creation IS NOT NULL 
          AND gr.created_at >= NOW() - INTERVAL {interval_str}
        GROUP BY gr.referral_source_at_creation
        ORDER BY count DESC
        LIMIT 5;
    """
    referrals_res = await db.fetch(sql_referrals)

    # 5. Free Usage Stats
    sql_free_usage = f"""
        SELECT
            COUNT(*) FILTER (WHERE trial_type = 'free_trial') AS free_trials_used,
            COUNT(*) FILTER (WHERE trial_type = 'whitelist') AS whitelist_uses
        FROM generations
        WHERE created_at >= NOW() - INTERVAL {interval_str};
    """
    free_usage_res = await db.fetchrow(sql_free_usage)

    # 6. Feature Usage
    sql_feature_usage = f"""
        SELECT
            type,
            COUNT(*) AS count
        FROM generations
        WHERE created_at >= NOW() - INTERVAL {interval_str}
        GROUP BY type;
    """
    feature_usage_res = await db.fetch(sql_feature_usage)

    # 7. Paid Tier Usage
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

    # Process results into dataclasses
    feature_usage_data = {row['type']: row['count'] for row in feature_usage_res.data}
    paid_tier_data = {f"quality_{row['quality_level']}": row['count'] for row in paid_tier_usage_res.data}

    return AnalyticsData(
        new_users=new_users_res.data["count"] if new_users_res.data else 0,
        funnel=FunnelStats(**funnel_res.data) if funnel_res.data else FunnelStats(),
        revenue=RevenueStats(total_stars=revenue_res.data["total"]) if revenue_res.data else RevenueStats(),
        free_usage=FreeUsageStats(**free_usage_res.data) if free_usage_res.data else FreeUsageStats(),
        feature_usage=FeatureUsageStats(**feature_usage_data),
        paid_tier_usage=PaidTierUsageStats(**paid_tier_data),
        top_referrals=[ReferralStats(**row) for row in referrals_res.data]
    )