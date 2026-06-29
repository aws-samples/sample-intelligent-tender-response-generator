import {Outlet, useNavigate} from "react-router-dom";
import {AppLayoutToolbar, BreadcrumbGroup, TopNavigation} from "@cloudscape-design/components";
import {signOutRedirect} from "../../utils/session";
import {useAuth} from "react-oidc-context";
import {CustomSideNavigation} from "./sideNavigation";
import {useState} from "react";


export const BaseLayout = () => {
    const auth = useAuth();
    const navigate = useNavigate();
    const [activeHref, setActiveHref] = useState("/analysis");

    async function handleButtonClick(event) {
        if (event.detail.id === 'signout') {
            await signOutRedirect(auth)
        }
    }

    function buildBreadcrumbs() {
        const paths = window.location.hash.split('/')

        let items = []
        let detail = ''
        let detailType = ''

        for (let path of paths) {
            if (path === 'analysis') {
                detailType = path
                items.push({text: 'Generated tender responses', href: '/analysis'})
            }
            else if (path === 'submitted-responses') {
                detailType = path
                items.push({text: 'Submitted tender responses', href: '/submitted-responses'})
            }
            else if (path === 'newAnalysis') {
                items.push({text: 'Generated tender responses', href: '/analysis'})
                items.push({text: 'New response', href: '/newAnalysis'})
            }
            else if (path === 'upload-files') {
                items.push({text: 'Upload files', href: `/analysis/${detail}/upload-files`})
            }
            else if (path === 'delete-files') {
                items.push({text: 'Delete files', href: `/analysis/${detail}/delete-files`})
            }
            else if (path !== '#' && path !== '') {
                items.push({text: path, href: `/${detailType}/${path}`})
                detail = path
            }
        }

        return (
            <BreadcrumbGroup
                items={items}
                onFollow={e => {
                    e.preventDefault();
                    navigate(e.detail.href);
                }}
            />
        )
    }

    return (
        <>
            <div id="h" style={{position: 'sticky', top: 0, zIndex: 1002}}>
                <TopNavigation
                    identity={{
                        href: '',
                        title: 'Intelligent Tender Response Generator',
                        onFollow: e => {e.preventDefault(); navigate('/analysis'); setActiveHref('/analysis')}
                    }}
                    utilities={[
                        {
                            type: 'menu-dropdown',
                            text: auth.user.profile.email,
                            iconName: 'user-profile',
                            onItemClick: handleButtonClick,
                            items: [{id: 'signout', text: 'Sign out'}]
                        }
                    ]}
                />
            </div>

            <AppLayoutToolbar
                headerSelector={'#h'}
                navigationHide={false}
                disableContentPaddings={false}
                navigation={<CustomSideNavigation activeHref={activeHref} setActiveHref={setActiveHref} />}
                toolsHide={true}
                breadcrumbs={buildBreadcrumbs()}
                content={<Outlet/>}
            />
        </>
    )
}
