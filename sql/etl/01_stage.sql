drop table if exists stg_prices;

create temp table stg_prices as
with fx as (  

    select distinct on (num_code, setting_date)
        num_code,
        setting_date,
        value
    from public.exchange_rates
    order by
        num_code,
        setting_date,
        id desc

)

select
    p.id as price_id,
    p.created_at,
    p.loading_date,
    p.end_loading_date,
    p.loading_city_gcid,
    p.unloading_city_gcid,
    p.distance,
    p.total_weight,
    p.total_volume,
    p.subscriber_id,
    p.organization_id,
    p.price_type,
    p.is_fact,
    p.complex,
    p.currency_code,
    p.price as price_orig,
    p.nearest_rate_date,
    p.outlier_mark,
    case
        when p.currency_code = '643' then 1.0
        else fx.value
    end as fx_rate,
    p.weight_category as weight_category_src,
    core.weight_category(p.total_weight) as weight_category_calc,
    p.volume_category as volume_category_src,
    core.volume_category(p.total_volume) as volume_category_calc,
    case
        when p.body_type is not null
            then core.body_group_of(coalesce(b0.std_id, p.body_type))
        else coalesce(
            (
                select core.body_group_of(coalesce(b.std_id, x.body_type_id))
                from public.price_body_types x
                left join public.body_types b on b.id = x.body_type_id
                where
                    x.price_id = p.id
                order by
                    x.body_type_id
                limit 1
            ),
            'Не указан'
        )
    end as body_group_primary,
    case
        when p.price <= 0 then 'PRICE_NONPOSITIVE'
        when p.currency_code = '643' and p.price <= 1000 then 'RUB_PRICE_LE_1000'
        when p.distance <= 0 then 'DISTANCE_NONPOSITIVE'
        when p.total_weight < 0 then 'NEGATIVE_WEIGHT'
        when p.total_volume < 0 then 'NEGATIVE_VOLUME'
        when lc.gc_id is null or uc.gc_id is null then 'CITY_NOT_FOUND'
        when p.currency_code not in ('643', '840', '978') then 'UNSUPPORTED_CURRENCY'
        when p.currency_code <> '643' and (fx.value is null or fx.value <= 0) then 'NO_FX_RATE'
    end as reason
from public.prices p
left join core.dim_city lc on lc.gc_id = p.loading_city_gcid
left join core.dim_city uc on uc.gc_id = p.unloading_city_gcid
left join public.body_types b0 on b0.id = p.body_type
left join fx on
    p.currency_code <> '643' and
    fx.num_code = p.currency_code and
    fx.setting_date = p.nearest_rate_date
where
    p.loading_date between %(start)s and %(end)s;
