delete from mart.mart_route_card;

insert into mart.mart_route_card (
    price_month,
    loading_city_gcid,
    loading_city,
    loading_region,
    unloading_city_gcid,
    unloading_city,
    unloading_region,
    body_group,
    weight_category,
    p25_trip,
    median_trip,
    p75_trip,
    avg_trip,
    p25_km,
    median_km,
    p75_km,
    trips_count,
    carriers_count,
    cv_rate,
    mom_pct,
    yoy_pct,
    series_last_date,
    freshness_days,
    reliability_level,
    as_of
)
with months as (  

    select
        price_id,
        price_month,
        max(price_date) as last_price_date
    from core.fact_price_month
    where
        price_date <= %(as_of)s
    group by
        price_id,
        price_month

), obs as (        

    select
        m.price_month,
        f.loading_city_gcid,
        f.unloading_city_gcid,
        bg.body_group,
        f.weight_category,
        f.price_rub,
        f.price_rub / nullif(f.distance, 0) as price_km,
        f.organization_id,
        f.price_type,
        m.last_price_date
    from months m
    inner join core.fact_price f on f.price_id = m.price_id
    inner join core.fact_price_body_group bg on bg.price_id = f.price_id
    where
        f.is_fact = true and
        f.complex = false and
        f.outlier_mark = false and
        f.price_rub > 0 and
        f.distance > 0

), cells as (

    select
        price_month,
        loading_city_gcid,
        unloading_city_gcid,
        body_group,
        weight_category,
        percentile_cont(0.25) within group (order by price_rub) as p25_trip,
        percentile_cont(0.50) within group (order by price_rub) as median_trip,
        percentile_cont(0.75) within group (order by price_rub) as p75_trip,
        avg(price_rub) as avg_trip,
        percentile_cont(0.25) within group (order by price_km) as p25_km,
        percentile_cont(0.50) within group (order by price_km) as median_km,
        percentile_cont(0.75) within group (order by price_km) as p75_km,
        count(*)::int as trips_count,
        (count(distinct organization_id) filter (where price_type in (3, 9)))::int as carriers_count,
        case
            when count(*) >= 2 and avg(price_rub) <> 0 then stddev_samp(price_rub) / avg(price_rub)
        end as cv_rate,
        max(last_price_date) as last_price_date
    from obs
    group by
        price_month,
        loading_city_gcid,
        unloading_city_gcid,
        body_group,
        weight_category

), series as (

    select
        c.*,
        max(c.last_price_date) over (
            partition by loading_city_gcid, unloading_city_gcid, body_group, weight_category
        ) as series_last_date
    from cells c

)

select
    c.price_month,
    c.loading_city_gcid,
    lc.city,
    lc.region,
    c.unloading_city_gcid,
    uc.city,
    uc.region,
    c.body_group,
    c.weight_category,
    c.p25_trip,
    c.median_trip,
    c.p75_trip,
    c.avg_trip,
    c.p25_km,
    c.median_km,
    c.p75_km,
    c.trips_count,
    c.carriers_count,
    c.cv_rate,
    case
        when prev.median_trip is not null and prev.median_trip <> 0
            then (c.median_trip / prev.median_trip - 1) * 100
    end as mom_pct,
    case
        when yoy.median_trip is not null and yoy.median_trip <> 0
            then (c.median_trip / yoy.median_trip - 1) * 100
    end as yoy_pct,
    c.series_last_date,
    (%(as_of)s::date - c.series_last_date)::int as freshness_days,
    case
        when c.trips_count >= 30 and c.carriers_count >= 5 and (%(as_of)s::date - c.series_last_date) <= 30 then 'HIGH'
        when c.trips_count >= 10 then 'MEDIUM'
        else 'LOW_DATA'
    end as reliability_level,
    %(as_of)s::date as as_of
from series c
inner join core.dim_city lc on lc.gc_id = c.loading_city_gcid
inner join core.dim_city uc on uc.gc_id = c.unloading_city_gcid
left join series prev on
    prev.loading_city_gcid = c.loading_city_gcid and
    prev.unloading_city_gcid = c.unloading_city_gcid and
    prev.body_group = c.body_group and
    prev.weight_category = c.weight_category and
    prev.price_month = (c.price_month - interval '1 month')::date
left join series yoy on
    yoy.loading_city_gcid = c.loading_city_gcid and
    yoy.unloading_city_gcid = c.unloading_city_gcid and
    yoy.body_group = c.body_group and
    yoy.weight_category = c.weight_category and
    yoy.price_month = (c.price_month - interval '12 months')::date;
