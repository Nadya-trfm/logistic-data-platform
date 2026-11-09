set -e

echo "Creating source schema..."
psql -v ON_ERROR_STOP=1 \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -f /source/schema.sql

echo "Generating synthetic data..."
psql -v ON_ERROR_STOP=1 \
    -v n_prices=300000 \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -f /source/synthetic.sql

echo "Database initialization completed!"