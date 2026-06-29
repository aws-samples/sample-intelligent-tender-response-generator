import {Autosuggest, TokenGroup} from "@cloudscape-design/components";

export const AutoSuggestTokenGroup = ({disabled, autoSuggestValue, setAutoSuggestValue, autoSuggestOptions, autoSuggestPlaceholder,
                                      selectedTokens, setSelectedTokens}) => {
    function addSelectedTokenIfNeeded(token) {
        for (const i in selectedTokens) {
            if (selectedTokens[i]['label'] === token.label) return
        }

        setSelectedTokens([...selectedTokens, {'label': token.label, 'value': token.value}])
    }

    return (
        <>
            <Autosuggest
                onChange={({detail}) => {setAutoSuggestValue(detail.value)}}
                onSelect={({detail: { selectedOption } }) => {
                    if (selectedOption !== undefined) {
                        addSelectedTokenIfNeeded(selectedOption)
                        setAutoSuggestValue('')
                    }}
                }
                value={autoSuggestValue}
                options={autoSuggestOptions}
                placeholder={autoSuggestPlaceholder}
                empty="No matches found"
                disabled={autoSuggestOptions.length === 0 || disabled}
                enteredTextLabel={value => `Use: "${value}"`}
            />

            <TokenGroup
                onDismiss={({detail: {itemIndex}}) => {
                    setSelectedTokens([
                        ...selectedTokens.slice(0, itemIndex),
                        ...selectedTokens.slice(itemIndex + 1)
                    ]);
                }}
                items={selectedTokens}
                disabled={disabled}
            />
        </>
    )
}