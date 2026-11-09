insert into dq.dq_quarantine_prices (
    price_id,
    loading_date,
    reason_code,
    currency_code,
    price,
    payload,
    etl_run_id
)
select
    s.price_id,
    s.loading_date,
    s.reason,
    s.currency_code,
    s.price_orig,
    to_jsonb(s) - 'reason',
    %(run_id)s
from stg_prices s
where
    s.reason is not null;
    