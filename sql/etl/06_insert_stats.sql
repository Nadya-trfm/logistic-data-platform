select
    count(*) as rows_read,
    count(*) filter (where reason is null) as rows_clean,
    count(*) filter (where reason is null and weight_category_src is null) as weight_cat_filled,
    count(*) filter (where reason is null and volume_category_src is null) as volume_cat_filled,
    count(*) filter (
        where
            reason is null and
            weight_category_src is not null and
            weight_category_src <> weight_category_calc
    ) as weight_cat_mismatch,
    count(*) filter (where reason is null and outlier_mark = true) as flagged_outliers
from stg_prices;
