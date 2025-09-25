
import React, {useState} from "react"
import Login from "../components/Login"
import Chatbot from "../components/Chatbot"

// Define page states as const object (enum alternative)
export const PageState = {
    LOGIN: 'login',
    CHATBOT: 'chatbot',
    // Add future states here:
    // PROFILE: 'profile',
    // SETTINGS: 'settings',
    // ORDER_HISTORY: 'order-history'
} as const;

// Create type from the const object
export type PageStateType = typeof PageState[keyof typeof PageState];

const Home: React.FC = () => {
    const [pageState, setPageState] = useState<PageStateType>(PageState.LOGIN);

    const renderPage = () => {
        switch (pageState) {
            case PageState.LOGIN:
                return <Login setPageState={setPageState} />;
            case PageState.CHATBOT:
                return <Chatbot setPageState={setPageState} />;
            // Future page cases:
            // case PageState.PROFILE:
            //     return <Profile setPageState={setPageState} />;
            // case PageState.SETTINGS:
            //     return <Settings setPageState={setPageState} />;
            // case PageState.ORDER_HISTORY:
            //     return <OrderHistory setPageState={setPageState} />;
            default:
                return <Login setPageState={setPageState} />;
        }
    };

    return (
        <div>
            {renderPage()}
        </div>
    )
}

export default Home
