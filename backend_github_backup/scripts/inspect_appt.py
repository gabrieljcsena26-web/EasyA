from app.db.database import SessionLocal
from app.models.models import Agendamento, Cliente, Funcionario, Estabelecimento

def main(appt_id=7):
    s = SessionLocal()
    ag = s.query(Agendamento).filter(Agendamento.id == appt_id).first()
    if not ag:
        print('Appointment not found')
        return
    print('Agendamento:', ag.to_dict())
    c = s.query(Cliente).filter(Cliente.id == ag.cliente_id).first()
    f = s.query(Funcionario).filter(Funcionario.id == ag.funcionario_id).first()
    print('Cliente:', {'id': c.id, 'estabelecimento_id': c.estabelecimento_id} if c else None)
    print('Funcionario:', {'id': f.id, 'estabelecimento_id': f.estabelecimento_id} if f else None)
    est = None
    if c:
        est = s.query(Estabelecimento).filter(Estabelecimento.id == c.estabelecimento_id).first()
    print('Cliente.estabelecimento:', est.id if est else None)
    s.close()

if __name__ == '__main__':
    main()
