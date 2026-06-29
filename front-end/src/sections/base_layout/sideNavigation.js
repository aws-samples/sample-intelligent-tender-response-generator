import {SideNavigation} from "@cloudscape-design/components";
import {useNavigate} from "react-router-dom";

export const CustomSideNavigation = ({activeHref, setActiveHref}) => {
    const navigate = useNavigate();

    return (
        <SideNavigation
            header={{
                href: '/analysis',
                text: 'Intelligent Tender Response Generator',
            }}
            items={[
                {type: 'link', text: `Generated tender responses`, href: '/analysis'},
                {type: 'link', text: `Submitted tender responses`, href: `/submitted-responses`}
            ]}
            activeHref={activeHref}
            onFollow={event => {
                if (!event.detail.external) {
                    event.preventDefault();
                    setActiveHref(event.detail.href);
                    navigate(event.detail.href);
                }
            }}
        />
    )
}