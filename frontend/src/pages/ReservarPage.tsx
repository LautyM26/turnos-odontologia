import { useParams } from "react-router";

export function ReservarPage() {
  const params = useParams();
  return (
    <section>
      <h1>Reservar turno</h1>
      <p>Token de reserva: {params.token}</p>
    </section>
  );
}
