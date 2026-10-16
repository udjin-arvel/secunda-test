from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ApiKeyDep, get_session
from app.schemas.payment import PaymentAccepted, PaymentCreate, PaymentDetail
from app.services import payment as payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={200: {"model": PaymentAccepted}},
)
async def create_payment(
    body: PaymentCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _: None = ApiKeyDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PaymentAccepted:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    payment, created = await payment_service.create_payment(session, body, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/{payment_id}", response_model=PaymentDetail)
async def get_payment(
    payment_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: None = ApiKeyDep,
) -> PaymentDetail:
    payment = await payment_service.get_by_id(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentDetail.model_validate(payment)
