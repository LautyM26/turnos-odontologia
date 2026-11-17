/**
 * Textos legales base (C-18, D8): versionados en código, sin datos reales.
 * Los datos del responsable van como marcadores `[A completar ...]` hasta que la asesoría legal
 * los valide (SU-08 / PA-04). Si cambia un texto, subir `version` y `fecha`.
 */

export const AVISO_LEGAL = "Texto base a validar con asesoría legal";

export interface Seccion {
  titulo: string;
  parrafos: string[];
}

export interface TextoLegal {
  version: string;
  fecha: string;
  secciones: Seccion[];
}

export const CUMPLIMIENTO: TextoLegal = {
  version: "1.0",
  fecha: "2026-11-17",
  secciones: [
    {
      titulo: "Ley 26.529: derechos del paciente e historia clínica",
      parrafos: [
        "La historia clínica es append-only: cada evolución queda con su autor profesional y su fecha y hora, y una corrección se registra como una entrada nueva, sin borrar la original.",
        "Cada lectura y escritura de la historia clínica queda en una auditoría inmutable.",
      ],
    },
    {
      titulo: "Ley 25.326: protección de datos personales",
      parrafos: [
        "Los datos de salud se tratan como datos sensibles: solo se cargan con el consentimiento del paciente y el acceso se limita por rol (la recepción no ve datos clínicos).",
        "Cada clínica tiene sus datos aislados de las demás. La política de privacidad es pública y declara dónde se guardan los datos.",
      ],
    },
    {
      titulo: "Ley 25.506: firma electrónica",
      parrafos: [
        "Los consentimientos informados se firman electrónicamente y dejan una constancia con fecha, IP, dispositivo y el hash del texto exacto firmado. Una vez firmado, el documento queda bloqueado y no se puede editar.",
      ],
    },
    {
      titulo: "Ley 27.706: receta electrónica",
      parrafos: [
        "La receta electrónica y las órdenes de estudios se emiten únicamente a través de una plataforma registrada en ReNaPDiS (partner). Sin partner configurado no se emite ninguna.",
      ],
    },
    {
      titulo: "Exportación sin retención",
      parrafos: [
        "La clínica puede exportar en cualquier momento una copia completa de sus datos (archivos CSV y adjuntos en un ZIP), sin costo y sin retención de información.",
      ],
    },
  ],
};

export const PRIVACIDAD: TextoLegal = {
  version: "1.0",
  fecha: "2026-11-17",
  secciones: [
    {
      titulo: "Responsable del tratamiento",
      parrafos: [
        "[A completar: razón social del responsable]. CUIT: [A completar: CUIT]. Domicilio: [A completar: domicilio]. Contacto: [A completar: email de contacto].",
      ],
    },
    {
      titulo: "Datos que tratamos",
      parrafos: [
        "Datos de identificación y contacto de pacientes y del personal, datos de turnos y datos de salud (historia clínica, odontograma, evoluciones y adjuntos). Los datos de salud son datos sensibles.",
      ],
    },
    {
      titulo: "Finalidad y consentimiento",
      parrafos: [
        "Usamos los datos para gestionar la atención odontológica, los turnos y los cobros. Los datos de salud solo se cargan con el consentimiento del paciente, que puede revocarse.",
      ],
    },
    {
      titulo: "Dónde se guardan tus datos",
      parrafos: [
        "Los datos se alojan en servidores en la nube del proveedor [A completar: proveedor y región], contratado por la plataforma. Los datos de cada clínica están aislados de los de las demás.",
      ],
    },
    {
      titulo: "Plazo de conservación",
      parrafos: ["La historia clínica se conserva por el plazo legal de [A completar: plazo]."],
    },
    {
      titulo: "Tus derechos",
      parrafos: [
        "Podés ejercer los derechos de acceso, rectificación y supresión de tus datos ante la clínica. La Agencia de Acceso a la Información Pública (AAIP) es el órgano de control de la Ley 25.326 y atiende denuncias y reclamos.",
      ],
    },
    {
      titulo: "Exportación de datos",
      parrafos: [
        "La clínica puede exportar una copia completa de sus datos en cualquier momento, sin costo y sin retención.",
      ],
    },
  ],
};
