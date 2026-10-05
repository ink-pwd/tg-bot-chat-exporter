import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from application.dto.login import (
    CodeDelivery,
    CodeSent,
    LoginCancelled,
    LoginCompleted,
    LoginStepResult,
    LoginTimedOut,
    PasswordRequired,
    QrRefreshed,
)
from application.errors import CodeExpired, InvalidCode, InvalidPassword
from application.use_cases.login_telegram_account import LoginTelegramAccount
from domain.errors import InvalidPhoneNumber
from presentation.telegram import texts
from presentation.telegram.callbacks import KeypadCallback, LoginCallback, MenuCallback
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus
from presentation.telegram.qr import qr_photo
from presentation.telegram.states import LoginStates

logger = logging.getLogger(__name__)
router = Router(name="login")

_MAX_CODE_LENGTH = 10


@router.callback_query(MenuCallback.filter(F.action == "add"))
async def choose_method(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await edit_or_answer(callback, texts.LOGIN_METHODS, menus.login_methods())


@router.callback_query(LoginCallback.filter(F.action == "cancel"))
async def cancel(callback: CallbackQuery, state: FSMContext, login: LoginTelegramAccount) -> None:
    await login.cancel(callback.from_user.id)
    await state.clear()
    await callback.answer(texts.LOGIN_CANCELLED)
    if callback.message is not None and callback.message.photo:
        await callback.message.delete()
    await edit_or_answer(callback, texts.MAIN_MENU, menus.main_menu())


# --- QR ---------------------------------------------------------------------


@router.callback_query(LoginCallback.filter(F.action == "qr"))
async def login_by_qr(
    callback: CallbackQuery, state: FSMContext, login: LoginTelegramAccount
) -> None:
    await state.clear()
    await callback.answer()
    user_id = callback.from_user.id
    challenge = await login.start_qr(user_id)
    await callback.message.delete()
    photo = await callback.message.answer_photo(
        qr_photo(challenge.url), caption=texts.QR_CAPTION, reply_markup=menus.login_cancel()
    )
    try:
        while True:
            result = await login.wait_qr(user_id)
            match result:
                case QrRefreshed(url=url):
                    try:
                        await photo.edit_media(
                            InputMediaPhoto(media=qr_photo(url), caption=texts.QR_CAPTION),
                            reply_markup=menus.login_cancel(),
                        )
                    except TelegramBadRequest:
                        # сообщение с QR удалено — пользователь ушёл
                        await login.cancel(user_id)
                        return
                case LoginCancelled():
                    await _safe_delete(photo)
                    return
                case LoginTimedOut():
                    await photo.delete()
                    await photo.answer(texts.QR_EXPIRED, reply_markup=menus.login_methods())
                    return
                case _:
                    await photo.delete()
                    await _after_sign_in(photo, state, result)
                    return
    except Exception:
        await _safe_delete(photo)
        raise


# --- телефон и код ----------------------------------------------------------


@router.callback_query(LoginCallback.filter(F.action == "phone"))
async def ask_phone(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LoginStates.phone)
    await callback.answer()
    await edit_or_answer(callback, texts.ASK_PHONE, menus.login_cancel())


@router.message(LoginStates.phone, F.text)
async def receive_phone(message: Message, state: FSMContext, login: LoginTelegramAccount) -> None:
    try:
        sent = await login.start_phone(message.from_user.id, message.text)
    except InvalidPhoneNumber as exc:
        await message.answer(texts.error_text(exc), reply_markup=menus.login_cancel())
        return
    await state.set_state(LoginStates.code)
    await _store_code_state(state, sent, code="")
    await message.answer(texts.code_prompt(sent, entered=0), reply_markup=menus.code_keypad())


@router.callback_query(LoginStates.code, KeypadCallback.filter())
async def keypad(
    callback: CallbackQuery,
    callback_data: KeypadCallback,
    state: FSMContext,
    login: LoginTelegramAccount,
) -> None:
    data = await state.get_data()
    sent = CodeSent(CodeDelivery(data["delivery"]), data["length"])
    code: str = data["code"]

    if callback_data.key == "del":
        code = code[:-1]
    elif callback_data.key.isdigit() and len(code) < _MAX_CODE_LENGTH:
        code += callback_data.key

    complete = callback_data.key == "ok" or (sent.length is not None and len(code) >= sent.length)
    if not complete or not code:
        await state.update_data(code=code)
        await callback.answer()
        await _edit_prompt(callback, sent, len(code))
        return

    await callback.answer()
    try:
        result = await login.submit_code(callback.from_user.id, code)
    except (InvalidCode, CodeExpired) as exc:
        await state.update_data(code="")
        await _edit_prompt(callback, sent, 0, notice=texts.error_text(exc))
        return
    await callback.message.delete()
    await _after_sign_in(callback.message, state, result)


@router.message(LoginStates.code)
async def code_sent_as_message(message: Message) -> None:
    await _safe_delete(message)
    await message.answer(texts.CODE_AS_MESSAGE)


@router.callback_query(LoginStates.code, LoginCallback.filter(F.action == "resend"))
async def resend_code(callback: CallbackQuery, state: FSMContext, login: LoginTelegramAccount) -> None:
    sent = await login.resend_code(callback.from_user.id)
    await _store_code_state(state, sent, code="")
    await callback.answer()
    await _edit_prompt(callback, sent, 0, notice="Код отправлен повторно.")


@router.callback_query(KeypadCallback.filter())
async def stale_keypad(callback: CallbackQuery) -> None:
    await callback.answer(texts.LOGIN_EXPIRED, show_alert=True)


# --- пароль 2FA -------------------------------------------------------------


@router.message(LoginStates.password, F.text)
async def receive_password(message: Message, state: FSMContext, login: LoginTelegramAccount) -> None:
    password = message.text
    try:
        await message.delete()
    except TelegramBadRequest:
        await message.answer(texts.PASSWORD_DELETE_HINT)
    try:
        result = await login.submit_password(message.from_user.id, password)
    except InvalidPassword as exc:
        await message.answer(texts.error_text(exc), reply_markup=menus.login_cancel())
        return
    await _after_sign_in(message, state, result)


# --- общее ------------------------------------------------------------------


async def _after_sign_in(message: Message, state: FSMContext, result: LoginStepResult) -> None:
    match result:
        case LoginCompleted(account=account):
            await state.clear()
            await message.answer(texts.account_connected(account), reply_markup=menus.main_menu())
        case PasswordRequired():
            await state.set_state(LoginStates.password)
            await state.set_data({})
            await message.answer(texts.ASK_PASSWORD, reply_markup=menus.login_cancel())


async def _store_code_state(state: FSMContext, sent: CodeSent, code: str) -> None:
    await state.set_data({"delivery": sent.delivery.value, "length": sent.length, "code": code})


async def _edit_prompt(
    callback: CallbackQuery, sent: CodeSent, entered: int, notice: str | None = None
) -> None:
    try:
        await callback.message.edit_text(
            texts.code_prompt(sent, entered, notice), reply_markup=menus.code_keypad()
        )
    except TelegramBadRequest:
        # «message is not modified» — текст не изменился
        pass


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
