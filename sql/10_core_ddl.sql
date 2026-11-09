create schema if not exists core;
create schema if not exists dq;
create schema if not exists mart;


create or replace function core.weight_category(w double precision) returns text
language sql immutable as $$
    select
        case
            when w is null then null
            when round(w::numeric, 1) >= 30 then 'G20T'
            when round(w::numeric, 1) >= 10 then 'FTL'
            when round(w::numeric, 1) >= 5 then '10T'
            when round(w::numeric, 1) >= 2.5 then '5T'
            when round(w::numeric, 1) >= 0.5 then 'L5T'
            else 'OTH'
        end
$$;

create or replace function core.volume_category(v double precision) returns text
language sql immutable as $$
    select
        case
            when v is null then null
            when v > 0 and v <= 120 then 'FTL'
            else 'OTH'
        end
$$;

create or replace function core.body_group_of(x integer) returns text
language sql immutable as $$
    select
        case
            when x is null then 'Не указан'
            when x in (56, 57, 58, 59, 60, 61) then 'Тент'
            when x in (4, 46, 47, 48) then 'Рефрижератор'
            when x = 2 then 'Изотерм'
            when x in (1, 15) then 'Борт'
            else 'Прочие'
        end
$$;

create table if not exists core.dim_city (
    gc_id integer primary key,
    source_city_id bigint not null,
    city text not null,
    region text not null,
    full_name_local text not null,
    latitude double precision,
    longitude double precision
);

create table if not exists core.fact_price (
    price_id bigint primary key,
    created_at timestamp(0),
    loading_date date not null,
    end_loading_date date,
    loading_city_gcid integer not null,   
    unloading_city_gcid integer not null,   
    distance double precision not null,
    total_weight double precision not null,
    total_volume double precision not null,
    subscriber_id integer,
    organization_id integer,
    price_type smallint not null,
    is_fact boolean not null,
    complex boolean not null,
    currency_code varchar(3) not null,
    price_orig double precision not null,
    fx_rate double precision not null,
    price_rub double precision not null,
    nearest_rate_date date,
    outlier_mark boolean not null,
    weight_category varchar(4) not null,
    volume_category varchar(4) not null,
    body_group_primary text not null,   
    etl_run_id text not null,
    loaded_at timestamptz not null default now()
);
create index if not exists fact_price_loading_date_idx on core.fact_price (loading_date);
create index if not exists fact_price_route_idx on core.fact_price (loading_city_gcid, unloading_city_gcid);

create table if not exists core.fact_price_body_group (
    price_id bigint not null references core.fact_price (price_id) on delete cascade,
    body_group text not null,
    primary key (price_id, body_group)
);

create table if not exists core.fact_price_month (
    price_id bigint not null references core.fact_price (price_id) on delete cascade,
    price_date date not null,
    price_month date not null,
    primary key (price_id, price_date)
);
create index if not exists fact_price_month_idx on core.fact_price_month (price_month);

create table if not exists dq.dq_quarantine_prices (
    price_id bigint primary key,
    loading_date date not null,
    reason_code text not null,
    currency_code varchar(3),
    price double precision,
    payload jsonb not null,
    etl_run_id text not null,
    quarantined_at timestamptz not null default now()
);
create index if not exists dq_quarantine_loading_date_idx on dq.dq_quarantine_prices (loading_date);

create table if not exists dq.run_log (
    id bigserial primary key,
    run_id text not null,
    stage text not null,
    window_start date,
    window_end date,
    rows_read integer,
    rows_loaded integer,
    rows_quarantined integer,
    details jsonb,
    started_at timestamptz not null,
    finished_at timestamptz not null default now()
);
