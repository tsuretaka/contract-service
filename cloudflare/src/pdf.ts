import { PDFDocument, StandardFonts, rgb } from 'pdf-lib';

const safe = (value: string | null | undefined) => (value ?? 'N/A').normalize('NFKD').replace(/[^\x20-\x7E]/g, '?');

export interface CertificateData {
  contractId: string; title: string; issuer: string; signer: string; signerEmail: string;
  originalSha256: string; signedAt: string; ipAddress: string; userAgent: string; auditHash: string;
}

export async function createSignedArtifacts(originalBytes: ArrayBuffer, data: CertificateData): Promise<{ certificate: Uint8Array; signed: Uint8Array }> {
  const certificateDoc = await PDFDocument.create();
  const font = await certificateDoc.embedFont(StandardFonts.Helvetica);
  const bold = await certificateDoc.embedFont(StandardFonts.HelveticaBold);
  const page = certificateDoc.addPage([595.28, 841.89]);
  page.drawRectangle({ x: 35, y: 35, width: 525, height: 772, borderColor: rgb(.7, .75, .82), borderWidth: 1.5 });
  page.drawText('Completion Certificate & Audit Record', { x: 105, y: 770, size: 18, font: bold, color: rgb(.1, .2, .4) });
  const rows = [
    ['Contract title', data.title], ['Contract ID', data.contractId], ['Issuer', data.issuer], ['Signer', data.signer],
    ['Signer email', data.signerEmail], ['Signed at (UTC)', data.signedAt], ['IP address', data.ipAddress],
    ['Original SHA-256', data.originalSha256], ['Audit record hash', data.auditHash], ['User agent', data.userAgent.slice(0, 80)]
  ];
  let y = 710;
  for (const [label, value] of rows) {
    page.drawText(`${label}:`, { x: 60, y, size: 9, font: bold });
    const text = safe(value);
    for (let offset = 0; offset < text.length; offset += 74) {
      page.drawText(text.slice(offset, offset + 74), { x: 175, y, size: 8.5, font });
      y -= 13;
    }
    y -= 15;
  }
  page.drawText('Generated from the tamper-evident audit chain. Verify the original SHA-256 before relying on this record.', { x: 60, y: 70, size: 7.5, font });
  const certificate = await certificateDoc.save();

  const signedDoc = await PDFDocument.load(originalBytes);
  const signedFont = await signedDoc.embedFont(StandardFonts.Helvetica);
  for (const contractPage of signedDoc.getPages()) {
    const width = contractPage.getWidth();
    const stamp = `E-SIGNED | ${data.signedAt} UTC | ID ${data.contractId} | SHA256 ${data.originalSha256}`;
    const size = Math.max(4, Math.min(6, (width - 32) / (stamp.length * .52)));
    contractPage.drawText(stamp, { x: 16, y: 8, size, font: signedFont, color: rgb(.4, .4, .4), opacity: .8 });
  }
  const [certificatePage] = await signedDoc.copyPages(certificateDoc, [0]);
  signedDoc.addPage(certificatePage);
  return { certificate, signed: await signedDoc.save() };
}
