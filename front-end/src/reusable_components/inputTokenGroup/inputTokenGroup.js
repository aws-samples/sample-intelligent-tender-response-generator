import {Button, Grid, Input, TokenGroup} from "@cloudscape-design/components";

export const InputTokenGroup = ({disabled, value, setValue, placeholder, tokens, setTokens}) => {
    function addSelectedTokenIfNeeded(token) {
        for (const i in tokens) {
            if (tokens[i]['label'] === token) return
        }

        setTokens([...tokens, {'label': token}])
    }

    return (
        <>
            <Grid
                gridDefinition={[{colspan: 9}, {colspan: 3}]}
            >
                <Input
                    onChange={({detail}) => setValue(detail.value)}
                    value={value}
                    inputMode="text"
                    placeholder={placeholder}
                    disabled={disabled}
                    onKeyDown={(event) => {
                        if (event.detail.key === 'Enter') {
                            addSelectedTokenIfNeeded(value)
                            setValue('')
                        }
                    }}
                />

                <Button
                    disabled={value.length === 0 || disabled}
                    onClick={() => {
                        addSelectedTokenIfNeeded(value)
                        setValue('')
                    }}
                >
                    Add
                </Button>
            </Grid>

            <TokenGroup
                onDismiss={({detail: {itemIndex}}) => {
                    setTokens([
                        ...tokens.slice(0, itemIndex),
                        ...tokens.slice(itemIndex + 1)
                    ]);
                }}
                items={tokens}
            />
        </>

    )
}