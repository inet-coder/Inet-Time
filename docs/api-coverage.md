# Telegram Bot API qamrovi (avtomatik hisobot)

`python tools/api_coverage.py --write docs/api-coverage.md` bilan yangilanadi.

**Metodlar: 33/142 (23%)** · update turlari: 5/23 (22%)

## Update turlari

✅ `message` ❌ `edited_message` ❌ `channel_post` ❌ `edited_channel_post` ❌ `business_connection` ❌ `business_message` ❌ `edited_business_message` ❌ `deleted_business_messages` ❌ `message_reaction` ❌ `message_reaction_count` ❌ `inline_query` ❌ `chosen_inline_result` ✅ `callback_query` ❌ `shipping_query` ✅ `pre_checkout_query` ❌ `purchased_paid_media` ❌ `poll` ✅ `poll_answer` ✅ `my_chat_member` ❌ `chat_member` ❌ `chat_join_request` ❌ `chat_boost` ❌ `removed_chat_boost`

## Update'lar va webhook (3/6)

✅ `getUpdates` ❌ `setWebhook` ✅ `deleteWebhook` ❌ `getWebhookInfo` ⛔ `logOut` ✅ `close`

## Bot haqida (3/14)

✅ `getMe` ✅ `setMyCommands` ❌ `deleteMyCommands` ❌ `getMyCommands` ❌ `setMyName` ❌ `getMyName` ❌ `setMyDescription` ❌ `getMyDescription` ❌ `setMyShortDescription` ❌ `getMyShortDescription` ✅ `setChatMenuButton` ❌ `getChatMenuButton` ❌ `setMyDefaultAdministratorRights` ❌ `getMyDefaultAdministratorRights`

## Xabar yuborish (18/23)

✅ `sendMessage` ❌ `forwardMessage` ❌ `forwardMessages` ✅ `copyMessage` ❌ `copyMessages` ✅ `sendPhoto` ✅ `sendAudio` ✅ `sendDocument` ✅ `sendVideo` ✅ `sendAnimation` ✅ `sendVoice` ✅ `sendVideoNote` ❌ `sendPaidMedia` ✅ `sendMediaGroup` ✅ `sendLocation` ✅ `sendVenue` ✅ `sendContact` ✅ `sendPoll` ✅ `sendDice` ✅ `sendChatAction` ✅ `setMessageReaction` ✅ `sendSticker` ⛔ `sendGame`

## Xabarni o'zgartirish (4/9)

✅ `editMessageText` ❌ `editMessageCaption` ✅ `editMessageMedia` ❌ `editMessageLiveLocation` ❌ `stopMessageLiveLocation` ✅ `editMessageReplyMarkup` ❌ `stopPoll` ✅ `deleteMessage` ❌ `deleteMessages`

## Fayl va foydalanuvchi (1/5)

✅ `getFile` ❌ `getUserProfilePhotos` ⛔ `setUserEmojiStatus` ❌ `getUserChatBoosts` ❌ `getBusinessConnection`

## Chat boshqaruvi (2/30)

❌ `banChatMember` ❌ `unbanChatMember` ❌ `restrictChatMember` ❌ `promoteChatMember` ❌ `setChatAdministratorCustomTitle` ❌ `banChatSenderChat` ❌ `unbanChatSenderChat` ❌ `setChatPermissions` ❌ `exportChatInviteLink` ❌ `createChatInviteLink` ❌ `editChatInviteLink` ❌ `createChatSubscriptionInviteLink` ❌ `editChatSubscriptionInviteLink` ❌ `revokeChatInviteLink` ❌ `approveChatJoinRequest` ❌ `declineChatJoinRequest` ❌ `setChatPhoto` ❌ `deleteChatPhoto` ❌ `setChatTitle` ❌ `setChatDescription` ❌ `pinChatMessage` ❌ `unpinChatMessage` ❌ `unpinAllChatMessages` ❌ `leaveChat` ✅ `getChat` ❌ `getChatAdministrators` ❌ `getChatMemberCount` ✅ `getChatMember` ❌ `setChatStickerSet` ❌ `deleteChatStickerSet`

## Forum mavzulari (0/13)

❌ `getForumTopicIconStickers` ❌ `createForumTopic` ❌ `editForumTopic` ❌ `closeForumTopic` ❌ `reopenForumTopic` ❌ `deleteForumTopic` ❌ `unpinAllForumTopicMessages` ❌ `editGeneralForumTopic` ❌ `closeGeneralForumTopic` ❌ `reopenGeneralForumTopic` ❌ `hideGeneralForumTopic` ❌ `unhideGeneralForumTopic` ❌ `unpinAllGeneralForumTopicMessages`

## Callback va inline (1/4)

✅ `answerCallbackQuery` ❌ `answerInlineQuery` ❌ `answerWebAppQuery` ❌ `savePreparedInlineMessage`

## To'lovlar va Stars (2/10)

✅ `sendInvoice` ❌ `createInvoiceLink` ❌ `answerShippingQuery` ✅ `answerPreCheckoutQuery` ❌ `getMyStarBalance` ❌ `getStarTransactions` ❌ `refundStarPayment` ❌ `editUserStarSubscription` ❌ `getAvailableGifts` ❌ `sendGift`

## Stikerlar (0/15)

❌ `getStickerSet` ❌ `getCustomEmojiStickers` ❌ `uploadStickerFile` ❌ `createNewStickerSet` ❌ `addStickerToSet` ❌ `setStickerPositionInSet` ❌ `deleteStickerFromSet` ❌ `replaceStickerInSet` ❌ `setStickerEmojiList` ❌ `setStickerKeywords` ❌ `setStickerMaskPosition` ❌ `setStickerSetTitle` ❌ `setStickerSetThumbnail` ❌ `setCustomEmojiStickerSetThumbnail` ❌ `deleteStickerSet`

## Business (0/17)

❌ `readBusinessMessage` ❌ `deleteBusinessMessages` ❌ `setBusinessAccountName` ❌ `setBusinessAccountUsername` ❌ `setBusinessAccountBio` ❌ `setBusinessAccountProfilePhoto` ❌ `removeBusinessAccountProfilePhoto` ❌ `setBusinessAccountGiftSettings` ❌ `getBusinessAccountStarBalance` ❌ `transferBusinessAccountStars` ❌ `getBusinessAccountGifts` ❌ `convertGiftToStars` ❌ `upgradeGift` ❌ `transferGift` ❌ `postStory` ❌ `editStory` ❌ `deleteStory`

## O'yinlar va Passport (ataylab qilinmaydi) (0/3)

⛔ `setGameScore` ⛔ `getGameHighScores` ⛔ `setPassportDataErrors`
