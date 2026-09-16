import { describe, expect, it } from 'vitest';
import { PDFDocument } from 'pdf-lib';
import { createSignedArtifacts } from '../src/pdf';

describe('signed PDF generation', () => {
  it('stamps every original page and appends a certificate', async () => {
    const original = await PDFDocument.create();
    original.addPage(); original.addPage();
    const bytes = await original.save();
    const result = await createSignedArtifacts(bytes.buffer as ArrayBuffer, {
      contractId: 'contract-1', title: 'NDA', issuer: 'Example Inc.', signer: 'Test Signer', signerEmail: 'signer@example.com',
      originalSha256: 'a'.repeat(64), signedAt: '2026-01-01T00:00:00.000Z', ipAddress: '127.0.0.1', userAgent: 'vitest', auditHash: 'b'.repeat(64)
    });
    expect((await PDFDocument.load(result.certificate)).getPageCount()).toBe(1);
    expect((await PDFDocument.load(result.signed)).getPageCount()).toBe(3);
  });
});
