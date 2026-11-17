/** Fixtures SINTÉTICAS tipadas con el contrato de la app (regla dura 14). */

import type {
  Adjunto,
  Evolucion,
  Ficha,
  Historia,
  Me,
  Odontograma,
  Paciente,
  Profesional,
} from "@/features/clinica/tipos";

export const meOdontologo: Me = {
  sub: 10,
  email: "odontologo@clinica-piloto.test",
  tenant_id: 1,
  roles: ["odontologo"],
};
export const meRecepcion: Me = {
  sub: 11,
  email: "recepcion@clinica-piloto.test",
  tenant_id: 1,
  roles: ["recepcionista"],
};
export const meAdmin: Me = {
  sub: 12,
  email: "admin@clinica-piloto.test",
  tenant_id: 1,
  roles: ["admin"],
};

export const profesionales: Profesional[] = [
  { id: 1, nombre: "Profesional Demo Uno", usuario_id: 10 },
  { id: 2, nombre: "Profesional Demo Dos", usuario_id: 20 },
];

export function paciente(extra: Partial<Paciente> = {}): Paciente {
  return {
    id: 7,
    nombre: "Demo",
    apellido: "Sintético Uno",
    dni: "99000001",
    email: "demo1@ejemplo.test",
    telefono: "+5491100000001",
    obra_social_nombre: "OS Ficticia",
    obra_social_plan: "Plan 1",
    nro_afiliado: "000111",
    riesgo_ausencia: 20,
    consentimiento_datos: true,
    consentimiento_datos_at: "2026-11-01T15:00:00Z",
    consentimiento_datos_por: 10,
    created_at: "2026-10-01T12:00:00Z",
    ...extra,
  };
}

export function ficha(extra: Partial<Ficha> = {}): Ficha {
  return {
    version: 0,
    anamnesis: null,
    alergias: null,
    antecedentes: null,
    autor_usuario_id: null,
    created_at: null,
    ...extra,
  };
}

export function odontograma(extra: Partial<Odontograma> = {}): Odontograma {
  return {
    id: null,
    version: 0,
    denticion: null,
    piezas: {},
    autor_usuario_id: null,
    created_at: null,
    ...extra,
  };
}

export function evolucion(extra: Partial<Evolucion> = {}): Evolucion {
  return {
    id: 1,
    paciente_id: 7,
    autor_usuario_id: 10,
    profesional_id: 1,
    fecha_hora: "2026-11-10T15:30:00Z",
    texto: "Control sintético, sin hallazgos",
    pieza_fdi: null,
    corrige_a_id: null,
    motivo_correccion: null,
    corregida_por_id: null,
    ...extra,
  };
}

export function historia(extra: Partial<Historia> = {}): Historia {
  return {
    ficha: ficha(),
    odontograma: odontograma(),
    evoluciones: [],
    next_cursor: null,
    ...extra,
  };
}

export function adjunto(extra: Partial<Adjunto> = {}): Adjunto {
  return {
    id: 1,
    paciente_id: 7,
    tipo: "pdf",
    mime: "application/pdf",
    tamano_bytes: 204_800,
    sha256: "0".repeat(64),
    subido_por: 10,
    created_at: "2026-11-10T15:30:00Z",
    ...extra,
  };
}
