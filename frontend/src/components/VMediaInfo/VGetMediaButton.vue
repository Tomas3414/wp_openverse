<script setup lang="ts">
import { useNuxtApp } from "#imports"

import type { SupportedMediaType } from "#shared/constants/media"
import type { Media } from "#shared/types/media"
import { useRouteResultParams } from "~/composables/use-route-result-params"

import VButton from "~/components/VButton.vue"

const props = defineProps<{
  media: Media
  mediaType: SupportedMediaType
}>()
const { resultParams } = useRouteResultParams()
const { $sendCustomEvent } = useNuxtApp()

const sendGetMediaEvent = () => {
  $sendCustomEvent("GET_MEDIA", {
    ...resultParams.value,
    provider: props.media.provider,
    mediaType: props.mediaType,
  })
}
</script>

<template>
  <VButton
    as="VLink"
    :href="media.foreign_landing_url"
    size="large"
    variant="filled-pink-8"
    has-icon-end
    show-external-icon
    :external-icon-size="6"
    class="description-bold"
    :send-external-link-click-event="false"
    @click="sendGetMediaEvent"
  >
    {{ $t(`${mediaType}Details.weblink`) }}
  </VButton>
</template>
