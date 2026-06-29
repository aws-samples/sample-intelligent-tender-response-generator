import {Navigate, Route, Routes} from "react-router-dom"
import {BaseLayout} from "../sections/base_layout/baseLayout";
import {AnalysisDetail} from "../sections/analysis_detail/content";
import {AnalysisFiles} from "../sections/analysis_files/content";
import {DeleteFiles} from "../sections/delete_files/content";
import {Home} from "../sections/home/content";
import {SubmittedResponses} from "../sections/submitted_responses/s3_browser";


export const PageRouter = () => {
    return (
        <Routes>
            <Route element={<BaseLayout />}>
                <Route path='/analysis' element={<Home/>} />
                <Route path='/submitted-responses' element={<SubmittedResponses/>} />
                <Route path='/submitted-responses/:folder' element={<SubmittedResponses/>} />
                <Route path='/analysis/:id' element={<AnalysisDetail/>} />
                <Route path='/newAnalysis' element={<AnalysisFiles/>} />
                <Route path='/analysis/:id/upload-files' element={<AnalysisFiles/>} />
                <Route path='/analysis/:id/delete-files' element={<DeleteFiles/>} />
                <Route path="*" element={<Navigate to="/analysis" replace />} />
            </Route>
        </Routes>
    )
}
