from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from application.services.user_timezones import UserTimezones
from application.use_cases.configure_auto_export import ConfigureAutoExport
from application.use_cases.manage_telegram_accounts import ManageTelegramAccounts
from presentation.telegram import texts
from presentation.telegram.callbacks import AccountCallback, MenuCallback
from presentation.telegram.handlers.common import edit_or_answer
from presentation.telegram.keyboards import menus

router = Router(name="accounts")


@router.callback_query(MenuCallback.filter(F.action == "accounts"))
async def list_accounts(callback: CallbackQuery, accounts: ManageTelegramAccounts) -> None:
    owned = await accounts.list(callback.from_user.id)
    await callback.answer()
    await edit_or_answer(
        callback, texts.ACCOUNTS if owned else texts.NO_ACCOUNTS, menus.accounts_list(owned)
    )


@router.callback_query(AccountCallback.filter(F.action == "open"))
async def open_account(
    callback: CallbackQuery,
    callback_data: AccountCallback,
    state: FSMContext,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    # сюда же ведёт «Отмена» из ввода даты — сбрасываем ожидание ввода
    await state.clear()
    await callback.answer()
    await show_account_card(
        callback, callback_data.account_id, accounts, auto_export, timezones
    )


async def show_account_card(
    callback: CallbackQuery,
    account_id: int,
    accounts: ManageTelegramAccounts,
    auto_export: ConfigureAutoExport,
    timezones: UserTimezones,
) -> None:
    user_id = callback.from_user.id
    account = await accounts.get(user_id, account_id)
    schedule = await auto_export.get(user_id, account_id)
    timezone = await timezones.get(user_id)
    await edit_or_answer(
        callback,
        texts.account_card(account, schedule, timezone),
        menus.account_card(account, schedule),
    )


@router.callback_query(AccountCallback.filter(F.action == "logout"))
async def ask_logout(
    callback: CallbackQuery, callback_data: AccountCallback, accounts: ManageTelegramAccounts
) -> None:
    account = await accounts.get(callback.from_user.id, callback_data.account_id)
    await callback.answer()
    await edit_or_answer(callback, texts.logout_confirm(account), menus.logout_confirm(account))


@router.callback_query(AccountCallback.filter(F.action == "logout_confirm"))
async def logout(
    callback: CallbackQuery, callback_data: AccountCallback, accounts: ManageTelegramAccounts
) -> None:
    await accounts.log_out(callback.from_user.id, callback_data.account_id)
    await callback.answer(texts.account_logged_out())
    owned = await accounts.list(callback.from_user.id)
    await edit_or_answer(
        callback, texts.ACCOUNTS if owned else texts.NO_ACCOUNTS, menus.accounts_list(owned)
    )
