delete from core.dim_city;
insert into core.dim_city (
    gc_id,
    source_city_id,
    city,
    region,
    full_name_local,
    latitude,
    longitude
)
select distinct on (c.gc_id)
    c.gc_id,
    c.id,
    coalesce(nullif(btrim(split_part(c.full_name_local, ',', 1)), ''), c.name),
    case
        when strpos(c.full_name_local, ',') > 0
            then coalesce(nullif(btrim(substr(c.full_name_local, strpos(c.full_name_local, ',') + 1)), ''), 'Не указан')
        else 'Не указан'
    end,
    c.full_name_local,
    c.latitude,
    c.longitude
from public.cities c
order by
    c.gc_id,
    c.id;
    