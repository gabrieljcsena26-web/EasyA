"""PDF Invoice Generator"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

class PDFGenerator:
    @staticmethod
    def generate_invoice_pdf(invoice: dict) -> bytes:
        """Generate invoice PDF."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Title
        c.setFont("Helvetica-Bold", 24)
        c.drawString(100, 750, "INVOICE")
        
        # Invoice details
        c.setFont("Helvetica", 12)
        c.drawString(100, 700, f"Invoice #: {invoice['invoice_number']}")
        c.drawString(100, 680, f"Date: {invoice['invoice_date']}")
        c.drawString(100, 660, f"Amount: ${invoice['amount']:.2f}")
        c.drawString(100, 640, f"Status: {invoice['payment_status']}")
        
        c.save()
        return buffer.getvalue()