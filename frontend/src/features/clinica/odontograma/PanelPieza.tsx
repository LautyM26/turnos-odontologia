/** Panel de edición de una pieza en <dialog> modal nativo (DF-8, DF-19). */

import { useEffect, useRef, useState } from "react";

import { DialogoConfirmacion } from "@/shared/ui/DialogoConfirmacion";

import type { Cara, EstadoCara, EstadoPieza, MarcaPieza, Registro } from "../tipos";
import { type Borrador, marcarCara, marcarPieza } from "./borrador";
import {
  ESTADOS_CARA,
  ESTADOS_PIEZA,
  ETIQUETA_CARA,
  ETIQUETA_REGISTRO,
  ORDEN_CARAS,
  SIN_CARAS,
} from "./fdi";

interface Props {
  pieza: number;
  caraInicial: Cara | null;
  borrador: Borrador;
  soloLectura: boolean;
  onCambiar: (b: Borrador) => void;
  onCerrar: () => void;
}

const REGISTROS: Registro[] = ["existente", "a_realizar"];

function SelectRegistro({
  id,
  label,
  value,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: Registro;
  disabled: boolean;
  onChange: (r: Registro) => void;
}) {
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-[13px] font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as Registro)}
      >
        {REGISTROS.map((r) => (
          <option key={r} value={r}>
            {ETIQUETA_REGISTRO[r]}
          </option>
        ))}
      </select>
    </>
  );
}

export function PanelPieza({
  pieza,
  caraInicial,
  borrador,
  soloLectura,
  onCambiar,
  onCerrar,
}: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [pendiente, setPendiente] = useState<MarcaPieza | null>(null);
  const actual = borrador.piezas[String(pieza)] ?? {};
  const estado = actual.estado ?? null;
  const tieneCaras = Object.keys(actual.caras ?? {}).length > 0;
  const sinCarasPorEstado = estado !== null && SIN_CARAS.includes(estado.codigo);

  // biome-ignore lint/correctness/useExhaustiveDependencies: solo al abrir
  useEffect(() => {
    const el = dialogo.current;
    if (el && !el.open) {
      el.showModal();
    }
    const destino = caraInicial ? `panel-cara-${caraInicial}` : "panel-estado";
    document.getElementById(destino)?.focus();
    return () => document.getElementById(`pieza-${pieza}`)?.focus();
  }, []);

  function cambiarEstado(codigo: string): void {
    if (codigo === "") {
      onCambiar(marcarPieza(borrador, pieza, null));
      return;
    }
    const marca: MarcaPieza = {
      codigo: codigo as EstadoPieza,
      registro: estado?.registro ?? "existente",
    };
    if (SIN_CARAS.includes(marca.codigo) && tieneCaras) {
      setPendiente(marca);
      return;
    }
    onCambiar(marcarPieza(borrador, pieza, marca));
  }

  return (
    <dialog
      ref={dialogo}
      aria-labelledby="panel-titulo"
      className="m-auto w-[min(32rem,95vw)] rounded-[20px] border border-border bg-surface p-6 text-foreground shadow-lg backdrop:bg-foreground/35 backdrop:backdrop-blur-[3px] motion-safe:animate-[aparecer_200ms_var(--ease-suave)]"
      onCancel={(e) => {
        e.preventDefault();
        onCerrar();
      }}
    >
      <h2 id="panel-titulo" className="text-lg font-semibold">
        Pieza {pieza}
      </h2>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label className="text-sm font-medium" htmlFor="panel-estado">
          Estado de la pieza
        </label>
        <select
          id="panel-estado"
          className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-[13px] font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
          value={estado?.codigo ?? ""}
          disabled={soloLectura}
          onChange={(e) => cambiarEstado(e.target.value)}
        >
          <option value="">Sin estado</option>
          {ESTADOS_PIEZA.map((e) => (
            <option key={e.codigo} value={e.codigo}>
              {e.etiqueta}
            </option>
          ))}
        </select>
        {estado && (
          <SelectRegistro
            id="panel-registro-pieza"
            label="Registro de la pieza"
            value={estado.registro}
            disabled={soloLectura}
            onChange={(r) =>
              onCambiar(marcarPieza(borrador, pieza, { codigo: estado.codigo, registro: r }))
            }
          />
        )}
      </div>
      <div className="mt-4 space-y-2">
        {ORDEN_CARAS.map((c) => {
          const marca = actual.caras?.[c];
          return (
            <div key={c} className="flex flex-wrap items-center gap-2">
              <label className="w-16 text-sm font-medium" htmlFor={`panel-cara-${c}`}>
                Cara {c}
              </label>
              <span className="w-32 text-sm text-muted">{ETIQUETA_CARA[c]}</span>
              <select
                id={`panel-cara-${c}`}
                className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 text-[13px] font-medium shadow-xs transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-55"
                value={marca?.codigo ?? ""}
                disabled={soloLectura || sinCarasPorEstado}
                onChange={(e) =>
                  onCambiar(
                    marcarCara(
                      borrador,
                      pieza,
                      c,
                      e.target.value === ""
                        ? null
                        : {
                            codigo: e.target.value as EstadoCara,
                            registro: marca?.registro ?? "existente",
                          },
                    ),
                  )
                }
              >
                <option value="">Sin marca</option>
                {ESTADOS_CARA.map((e) => (
                  <option key={e.codigo} value={e.codigo}>
                    {e.etiqueta}
                  </option>
                ))}
              </select>
              {marca && (
                <SelectRegistro
                  id={`panel-registro-${c}`}
                  label={`Registro de la cara ${c}`}
                  value={marca.registro}
                  disabled={soloLectura}
                  onChange={(r) =>
                    onCambiar(marcarCara(borrador, pieza, c, { codigo: marca.codigo, registro: r }))
                  }
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-5 flex justify-end">
        <button
          type="button"
          className="rounded bg-primary px-4 py-2 text-primary-foreground"
          onClick={onCerrar}
        >
          Listo
        </button>
      </div>
      <DialogoConfirmacion
        abierto={pendiente !== null}
        titulo="Quitar marcas de las caras"
        confirmar={`Marcar ${pendiente ? (ESTADOS_PIEZA.find((e) => e.codigo === pendiente.codigo)?.etiqueta ?? "").toLowerCase() : ""}`}
        onConfirmar={() => {
          if (pendiente) onCambiar(marcarPieza(borrador, pieza, pendiente));
          setPendiente(null);
        }}
        onCancelar={() => setPendiente(null)}
      >
        Se quitarán las marcas de las caras de la pieza {pieza}: una pieza ausente o extraída no
        tiene caras marcadas.
      </DialogoConfirmacion>
    </dialog>
  );
}
