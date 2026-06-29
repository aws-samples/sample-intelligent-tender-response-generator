import {useNavigate} from "react-router-dom";
import {Link} from "@cloudscape-design/components";

export const CustomLink = (props) => {
    let navigate = useNavigate()

    return (
        <Link
            {...props}
            onFollow={event => {
                if (!event.detail.external) {
                    event.preventDefault()
                    navigate(event.detail.href)
                }
            }}
        >
            {props.children}
        </Link>
    )
}