insert into core.fact_price_body_group (price_id, body_group)
select
    price_id,
    body_group
from (
    select
        s.price_id,
        core.body_group_of(coalesce(b.std_id, x.body_type_id)) as body_group
    from stg_prices s
    inner join public.price_body_types x on x.price_id = s.price_id
    left join public.body_types b on b.id = x.body_type_id
    where
        s.reason is null
    union
    select
        s.price_id,
        s.body_group_primary
    from stg_prices s
    where
        s.reason is null and
        not exists (
            select 1
            from public.price_body_types x
            where
                x.price_id = s.price_id
        )
) u;

insert into core.fact_price_month (price_id, price_date, price_month)
select
    d.price_id,
    d.price_date,
    date_trunc('month', d.price_date)::date
from public.price_dates d
inner join stg_prices s on s.price_id = d.price_id and s.reason is null;
