import { useParams } from "react-router";

export function ComprobantePage() {
  const params = useParams();
  return (
    <section>
      <h1>Comprobante</h1>
      <p>Comprobante: {params.id}</p>
    </section>
  );
}
