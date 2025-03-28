import { navigateTo } from "#imports"
import { computed, watch } from "vue"

import { useSearchStore } from "~/stores/search"
import { useMediaStore } from "~/stores/media"
import { useI18nResultsCount } from "~/composables/use-i18n-utilities"
import { useMatchSearchRoutes } from "~/composables/use-match-routes"
import { useAnalytics } from "~/composables/use-analytics"

export const useSearch = (
  sendCustomEvent: ReturnType<typeof useAnalytics>["sendCustomEvent"]
) => {
  const mediaStore = useMediaStore()
  const searchStore = useSearchStore()

  const { matches: isSearchRoute } = useMatchSearchRoutes()

  const storeSearchTerm = computed(() => searchStore.searchTerm)

  /**
   * To update the local search term when the route changes, when, for example,
   * the user clicks the back button, we need to watch the store search term.
   */
  watch(storeSearchTerm, (newSearchTerm) => {
    searchTerm.value = newSearchTerm
  })

  /**
   * Search term has a getter and setter to be used as a v-model.
   * To prevent sending unnecessary requests, we also keep track of whether
   * the search term was changed.
   */
  const searchTerm = computed({
    get: () => searchStore.localSearchTerm,
    set: (value: string) => {
      searchStore.localSearchTerm = value
    },
  })

  const searchTermChanged = computed(
    () => searchStore.searchTerm !== searchTerm.value
  )

  /**
   * Called when the 'search' button is clicked in the header.
   *
   * No op if the search term is blank.
   * If the search term hasn't changed from the store version, we do nothing on
   * a search route. On other routes, we set the search type to 'All content' and
   * reset the media.
   *
   * Then, we update the search term, and update the path.
   *
   * Updating the path causes the `search.vue` page's route watcher
   * to run and fetch new media.
   */
  const updateSearchState = () => {
    if (searchTerm.value === "") {
      return
    }
    if (!searchTermChanged.value && isSearchRoute.value) {
      return
    }

    sendCustomEvent("SUBMIT_SEARCH", {
      searchType: searchStore.searchType,
      query: searchTerm.value,
    })

    const searchPath = searchStore.updateSearchPath({
      searchTerm: searchTerm.value,
    })
    return navigateTo(searchPath)
  }

  const resultsCount = computed(() => mediaStore.resultCount)
  const showLoading = computed(() => mediaStore.showLoading)

  const { getI18nCount } = useI18nResultsCount(showLoading)
  /**
   * Additional text at the end of the search bar.
   * Shows the loading state or result count.
   */
  const searchStatus = computed(() => {
    if (searchStore.searchTerm === "") {
      return ""
    }
    return getI18nCount(resultsCount.value)
  })

  return {
    updateSearchState,
    searchTerm,
    searchStatus,
  }
}
