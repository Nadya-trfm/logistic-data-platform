create schema if not exists mart;

create table if not exists mart.mart_route_card (
    price_month date not null,
    loading_city_gcid integer not null,
    loading_city text not null,
    loading_region text not null,
    unloading_city_gcid integer not null,
    unloading_city text not null,
    unloading_region text not null,
    body_group text not null,
    weight_category varchar(4) not null,
    p25_trip double precision,
    median_trip double precision,
    p75_trip double precision,
    avg_trip double precision,
    p25_km double precision,
    median_km double precision,
    p75_km double precision,
    trips_count integer not null,
    carriers_count integer not null,
    cv_rate double precision,
    mom_pct double precision,
    yoy_pct double precision,
    series_last_date date not null,   
    freshness_days integer not null,   
    reliability_level text not null,
    as_of date not null,
    built_at timestamptz not null default now(),
    primary key (price_month, loading_city_gcid, unloading_city_gcid, body_group, weight_category)
);
create index if not exists route_card_series_idx
    on mart.mart_route_card (
        loading_city_gcid,
        unloading_city_gcid,
        body_group,
        weight_category,
        price_month
    );

create or replace view mart.mart_market_corridor as
select distinct on (loading_city_gcid, unloading_city_gcid, body_group, weight_category)
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
    reliability_level,
    freshness_days,
    as_of
from mart.mart_route_card
order by
    loading_city_gcid,
    unloading_city_gcid,
    body_group,
    weight_category,
    price_month desc;

create table if not exists mart.ml_price_predictions (
    price_id bigint not null,
    model_name text not null,
    split text not null check (split in ('test', 'future')),
    loading_date date not null,
    loading_city_gcid integer not null,
    unloading_city_gcid integer not null,
    body_group text not null,
    outlier_mark boolean not null,
    actual_price_rub double precision,
    predicted_price_rub double precision not null,
    abs_error_rub double precision,
    ape_pct double precision,
    scored_at timestamptz not null default now(),
    primary key (price_id, model_name)
);
create index if not exists ml_pred_loading_date_idx on mart.ml_price_predictions (loading_date);

create table if not exists mart.ml_model_metrics (
    model_name text not null,
    split text not null,
    n_rows integer not null,
    r2 double precision,
    mape_pct double precision,
    rmse_rub double precision,
    mae_rub double precision,
    train_from date,
    train_to date,
    test_from date,
    test_to date,
    trained_at timestamptz not null default now(),
    primary key (model_name, split)
);
