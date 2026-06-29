import {Button, Select, SpaceBetween,} from "@cloudscape-design/components";

const CategorySelect = ({options, onOptionSelected, file}) => {
    return <Select
        disabled={file.loading}
        expandToViewport={true}
        selectedOption={file.category == null? {} : file.category}
        options={options}
        onChange={({ detail }) =>
            onOptionSelected(file, detail.selectedOption)
        }
    ></Select>
}


export function buildColumnDefinitions(fileCategories, onOptionSelected) {
    const rawColumns = [
        {
            id: 'category',
            header: 'File category',
            cell: item => (
                <SpaceBetween direction="horizontal" size="xs">
                    <CategorySelect file={item} options={fileCategories} onOptionSelected={onOptionSelected}></CategorySelect>

                    {item.category &&
                        <Button disabled={item.loading} iconName="remove" variant="link" onClick={() => onOptionSelected(item, null)}/>
                    }
                </SpaceBetween>
            )
        },
    ];

    return rawColumns.map(column => ({...column}));
}