select
    price_month,
    p25_trip,
    median_trip,
    p75_trip,
    median_km,
    trips_count,
    carriers_count,
    round(mom_pct::numeric, 1) as mom_pct,
    round(yoy_pct::numeric, 1) as yoy_pct,
    reliability_level
from mart.mart_route_card
where
    loading_city_gcid = 1001 and
    unloading_city_gcid = 1003 and
    body_group = 'Тент' and
    weight_category = 'FTL'
order by
    price_month desc
limit 12;

select
    loading_city,
    unloading_city,
    body_group,
    weight_category,
    price_month,
    round(p25_trip::numeric),
    round(median_trip::numeric),
    round(p75_trip::numeric),
    trips_count,
    carriers_count
from mart.mart_market_corridor
where
    reliability_level = 'HIGH'
order by
    trips_count desc
limit 20;

select
    price_id,
    loading_date,
    body_group,
    actual_price_rub,
    predicted_price_rub,
    round(ape_pct::numeric, 1) as ape_pct
from mart.ml_price_predictions
where
    split = 'test' and
    outlier_mark = false and
    actual_price_rub > 1.25 * predicted_price_rub
order by
    ape_pct desc
limit 20;
