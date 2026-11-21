"""Contractor accountability and repeat defect detection."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from app.models import Ticket, WorkOrder, Contractor
from app.services.duplicates import check_repeat_defect


def check_warranty_period(work_order: WorkOrder, current_date: datetime) -> bool:
    """Check if work order is still within warranty period."""
    warranty_end = work_order.completion_date + timedelta(days=work_order.warranty_months * 30)
    return current_date <= warranty_end


def find_responsible_contractor(
    db: Session,
    ticket: Ticket
) -> Optional[Dict]:
    """
    Find if this ticket is a repeat defect and identify responsible contractor.
    
    Returns contractor info if found, None otherwise.
    """
    # Check for resolved tickets at same location
    original = check_repeat_defect(
        db,
        ticket.lat,
        ticket.lng,
        ticket.category,
        months_back=12,
        radius_m=20.0
    )
    
    if not original:
        return None
    
    # Find work order linked to original ticket
    work_order = db.query(WorkOrder).filter(
        WorkOrder.ticket_id == original.id
    ).first()
    
    if not work_order:
        return None
    
    # Check if still in warranty
    in_warranty = check_warranty_period(work_order, datetime.utcnow())
    
    # Get contractor details
    contractor = db.query(Contractor).filter(
        Contractor.id == work_order.contractor_id
    ).first()
    
    if not contractor:
        return None
    
    return {
        'contractor': {
            'id': contractor.id,
            'name': contractor.name,
            'registration_number': contractor.registration_number,
            'contact_person': contractor.contact_person,
            'phone': contractor.phone,
            'is_blacklisted': contractor.is_blacklisted
        },
        'work_order': {
            'id': work_order.id,
            'completion_date': work_order.completion_date.isoformat(),
            'warranty_months': work_order.warranty_months,
            'in_warranty': in_warranty,
            'cost': work_order.cost
        },
        'original_ticket': {
            'id': original.id,
            'created_at': original.created_at.isoformat(),
            'resolved_at': original.created_at.isoformat(),  # Approximate
            'before_image': original.before_image,
            'after_image': original.after_image
        }
    }


def generate_evidence_report(
    db: Session,
    ticket: Ticket,
    contractor_info: Dict
) -> Dict:
    """
    Generate evidence report for repeat defect.
    
    Returns structured data for PDF generation.
    """
    report = {
        'report_date': datetime.utcnow().isoformat(),
        'report_title': f'Repeat Defect Evidence Report - Ticket #{ticket.id}',
        
        'current_complaint': {
            'ticket_id': ticket.id,
            'category': ticket.category,
            'location': {
                'lat': ticket.lat,
                'lng': ticket.lng
            },
            'reported_at': ticket.created_at.isoformat(),
            'reporter_count': ticket.reporter_count,
            'before_image': ticket.before_image,
            'severity': ticket.severity
        },
        
        'original_repair': contractor_info['original_ticket'],
        'contractor': contractor_info['contractor'],
        'work_order': contractor_info['work_order'],
        
        'analysis': {
            'is_warranty_claim': contractor_info['work_order']['in_warranty'],
            'time_since_repair_days': (
                datetime.utcnow() - 
                datetime.fromisoformat(contractor_info['work_order']['completion_date'])
            ).days,
            'same_location': True,
            'same_issue_type': True
        },
        
        'recommendations': []
    }
    
    # Add recommendations based on analysis
    if report['analysis']['is_warranty_claim']:
        report['recommendations'].append(
            "This defect is within warranty period. Contractor should repair at no additional cost."
        )
    else:
        report['recommendations'].append(
            "Warranty period has expired. New tender may be required."
        )
    
    if contractor_info['contractor']['is_blacklisted']:
        report['recommendations'].append(
            "WARNING: This contractor is currently blacklisted. Review previous performance."
        )
    
    days_since = report['analysis']['time_since_repair_days']
    if days_since < 90:
        report['recommendations'].append(
            f"Defect reappeared within {days_since} days. Indicates possible poor quality work."
        )
    
    return report


def generate_evidence_pdf(report: Dict, output_path: Path) -> Path:
    """
    Generate PDF evidence report using WeasyPrint.
    
    Returns path to generated PDF.
    """
    try:
        from weasyprint import HTML
        from io import StringIO
        
        # Generate HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{report['report_title']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid #3498db; }}
                .warning {{ background: #fff3cd; border-left-color: #ffc107; }}
                .info {{ display: grid; grid-template-columns: 200px 1fr; gap: 10px; }}
                .info dt {{ font-weight: bold; }}
                .recommendation {{ padding: 10px; margin: 10px 0; background: #e3f2fd; border-left: 4px solid #2196f3; }}
                img {{ max-width: 400px; border: 1px solid #ddd; margin: 10px 0; }}
                .images {{ display: flex; gap: 20px; flex-wrap: wrap; }}
            </style>
        </head>
        <body>
            <h1>{report['report_title']}</h1>
            <p><strong>Generated:</strong> {report['report_date']}</p>
            
            <div class="section">
                <h2>Current Complaint</h2>
                <dl class="info">
                    <dt>Ticket ID:</dt><dd>#{report['current_complaint']['ticket_id']}</dd>
                    <dt>Category:</dt><dd>{report['current_complaint']['category']}</dd>
                    <dt>Reported:</dt><dd>{report['current_complaint']['reported_at']}</dd>
                    <dt>Reporters:</dt><dd>{report['current_complaint']['reporter_count']} people</dd>
                    <dt>Severity:</dt><dd>{report['current_complaint']['severity']}/10</dd>
                    <dt>Location:</dt><dd>{report['current_complaint']['location']['lat']}, {report['current_complaint']['location']['lng']}</dd>
                </dl>
            </div>
            
            <div class="section">
                <h2>Original Repair History</h2>
                <dl class="info">
                    <dt>Original Ticket:</dt><dd>#{report['original_repair']['id']}</dd>
                    <dt>Repair Date:</dt><dd>{report['original_repair']['resolved_at']}</dd>
                </dl>
            </div>
            
            <div class="section {'warning' if report['contractor']['is_blacklisted'] else ''}">
                <h2>Contractor Information</h2>
                <dl class="info">
                    <dt>Name:</dt><dd>{report['contractor']['name']}</dd>
                    <dt>Registration:</dt><dd>{report['contractor']['registration_number']}</dd>
                    <dt>Contact Person:</dt><dd>{report['contractor']['contact_person']}</dd>
                    <dt>Phone:</dt><dd>{report['contractor']['phone']}</dd>
                    <dt>Status:</dt><dd>{"⚠️ BLACKLISTED" if report['contractor']['is_blacklisted'] else "Active"}</dd>
                </dl>
            </div>
            
            <div class="section">
                <h2>Work Order Details</h2>
                <dl class="info">
                    <dt>Work Order ID:</dt><dd>#{report['work_order']['id']}</dd>
                    <dt>Completion Date:</dt><dd>{report['work_order']['completion_date']}</dd>
                    <dt>Warranty Period:</dt><dd>{report['work_order']['warranty_months']} months</dd>
                    <dt>In Warranty:</dt><dd>{"✅ Yes" if report['work_order']['in_warranty'] else "❌ No"}</dd>
                    <dt>Original Cost:</dt><dd>₹{report['work_order']['cost']:,.2f}</dd>
                </dl>
            </div>
            
            <div class="section">
                <h2>Analysis</h2>
                <dl class="info">
                    <dt>Time Since Repair:</dt><dd>{report['analysis']['time_since_repair_days']} days</dd>
                    <dt>Same Location:</dt><dd>{"✅ Yes" if report['analysis']['same_location'] else "❌ No"}</dd>
                    <dt>Same Issue Type:</dt><dd>{"✅ Yes" if report['analysis']['same_issue_type'] else "❌ No"}</dd>
                    <dt>Warranty Claim:</dt><dd>{"✅ Valid" if report['analysis']['is_warranty_claim'] else "❌ Expired"}</dd>
                </dl>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                {"".join(f'<div class="recommendation">• {rec}</div>' for rec in report['recommendations'])}
            </div>
            
            <div class="section">
                <h2>Evidence Photos</h2>
                <p><em>Note: Photos should be reviewed in the system for full resolution</em></p>
                <dl class="info">
                    <dt>Original Before:</dt><dd>{report['original_repair']['before_image']}</dd>
                    <dt>Original After:</dt><dd>{report['original_repair']['after_image'] or 'N/A'}</dd>
                    <dt>New Complaint:</dt><dd>{report['current_complaint']['before_image']}</dd>
                </dl>
            </div>
            
            <hr style="margin: 40px 0;">
            <p style="color: #7f8c8d; font-size: 12px;">
                This report is generated automatically by CivicLoop and should be reviewed by 
                a qualified engineer before taking action. The system provides evidence for 
                human decision-making, not automated judgments.
            </p>
        </body>
        </html>
        """
        
        # Generate PDF
        HTML(string=html_content).write_pdf(output_path)
        return output_path
        
    except Exception as e:
        # Fallback: save HTML if PDF generation fails
        html_path = output_path.with_suffix('.html')
        html_path.write_text(html_content)
        return html_path
