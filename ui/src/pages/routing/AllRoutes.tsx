import React from 'react'
import { Routes, Route } from 'react-router-dom'

const Home = React.lazy(() => import('../Home'));


const AllRoutes = () => (
    <Routes>
        <Route path="/" element={<Home />} />
    </Routes>
)

AllRoutes.displayName = 'AllRoutes'

export default AllRoutes