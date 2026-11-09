delete from core.fact_price
where
    loading_date between %(start)s and %(end)s;
delete from dq.dq_quarantine_prices
where
    loading_date between %(start)s and %(end)s;
    