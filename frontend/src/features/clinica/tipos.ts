/**
 * Contrato HTTP consumido por la UI clínica (C-08 + C-09), en un solo archivo.
 * Fuente: backend/app/domain/pacientes/schemas.py y backend/app/domain/clinica/schemas.py.
 */

export type Rol = "admin" | "odontologo" | "recepcionista" | "paciente-enlace";

export interface Me {
  sub: number;
  email: string;
  tenant_id: number;
  roles: Rol[];
}

export interface Pagina<T> {
  items: T[];
  next_cursor: number | null;
}

export interface Paciente {
  id: number;
  nombre: string;
  apellido: string;
  dni: string;
  email: string | null;
  telefono: string | null;
  obra_social_nombre: string | null;
  obra_social_plan: string | null;
  nro_afiliado: string | null;
  riesgo_ausencia: number;
  consentimiento_datos: boolean;
  consentimiento_datos_at: string | null;
  consentimiento_datos_por: number | null;
  created_at: string;
}

/** Campos editables por PATCH (solo se envían los tocados). */
export type PacientePatch = Partial<
  Pick<
    Paciente,
    | "nombre"
    | "apellido"
    | "dni"
    | "email"
    | "telefono"
    | "obra_social_nombre"
    | "obra_social_plan"
    | "nro_afiliado"
    | "consentimiento_datos"
  >
>;

export interface Ficha {
  version: number;
  anamnesis: string | null;
  alergias: string | null;
  antecedentes: string | null;
  autor_usuario_id: number | null;
  created_at: string | null;
}

export interface FichaPut {
  version_esperada: number;
  anamnesis: string | null;
  alergias: string | null;
  antecedentes: string | null;
}

export interface Adjunto {
  id: number;
  paciente_id: number;
  tipo: string;
  mime: string;
  tamano_bytes: number;
  sha256: string;
  subido_por: number;
  created_at: string;
}

export interface Profesional {
  id: number;
  nombre: string;
  usuario_id: number | null;
}

export type Cara = "V" | "L" | "M" | "D" | "O";
export type Denticion = "permanente" | "temporal" | "mixta";
export type Registro = "existente" | "a_realizar";
export type EstadoPieza =
  | "ausente"
  | "extraida"
  | "extraccion_indicada"
  | "corona"
  | "endodoncia"
  | "implante";
export type EstadoCara = "caries" | "obturacion" | "sellador" | "fractura";

export interface MarcaPieza {
  codigo: EstadoPieza;
  registro: Registro;
}
export interface MarcaCara {
  codigo: EstadoCara;
  registro: Registro;
}
export interface Pieza {
  estado?: MarcaPieza | null;
  caras?: Partial<Record<Cara, MarcaCara>>;
}
export type Piezas = Record<string, Pieza>;

export interface OdontogramaIn {
  version_esperada: number;
  denticion: Denticion;
  piezas: Piezas;
}

export interface Odontograma {
  id: number | null;
  version: number;
  denticion: Denticion | null;
  piezas: Piezas;
  autor_usuario_id: number | null;
  created_at: string | null;
}

export interface Evolucion {
  id: number;
  paciente_id: number;
  autor_usuario_id: number;
  profesional_id: number;
  fecha_hora: string;
  texto: string;
  pieza_fdi: number | null;
  corrige_a_id: number | null;
  motivo_correccion: string | null;
  corregida_por_id: number | null;
}

export interface EvolucionIn {
  texto: string;
  pieza_fdi?: number | null;
  corrige_a_id?: number;
  motivo_correccion?: string;
}

export interface Historia {
  ficha: Ficha;
  odontograma: Odontograma;
  evoluciones: Evolucion[];
  next_cursor: number | null;
}
