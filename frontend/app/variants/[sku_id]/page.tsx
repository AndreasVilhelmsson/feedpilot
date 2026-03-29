export default function VariantManagerPage({
  params,
}: {
  params: { sku_id: string }
}) {
  return (
    <div className="p-8">
      <h1 className="font-display text-2xl font-bold text-on-surface">
        Variant Manager
      </h1>
      <p className="mt-2 text-on-surface-variant">SKU: {params.sku_id}</p>
    </div>
  )
}
