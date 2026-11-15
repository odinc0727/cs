CREATE TABLE IF NOT EXISTS public.products (
    uid         uuid PRIMARY KEY DEFAULT uuidv7(),
    name        text NOT NULL,
    price_cents integer NOT NULL CHECK (price_cents >= 0),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Seed once, before Debezium starts, so the first event is an initial snapshot (op=r).
INSERT INTO public.products (name, price_cents)
SELECT '初始快照商品', 9900
WHERE NOT EXISTS (SELECT 1 FROM public.products);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'cdc_products_publication') THEN
        CREATE PUBLICATION cdc_products_publication FOR TABLE public.products;
    END IF;
END $$;
